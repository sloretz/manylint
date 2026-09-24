# Copyright 2026 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


@dataclass
class HookResult:
    """Represents the result of running a single pre-commit or manylint hook on a target."""

    target_name: str
    hook_id: str
    returncode: int
    duration: float
    stdout: str
    stderr: str
    xunit_file: Path | None = None


def build_aggregated_junit_xml(
    results_by_target: dict[str, list[HookResult]],
    junit_dir_by_target: dict[str, Path],
) -> str:
    """Combine all per-linter .xunit.xml files and fallback hook results into JUnit XML."""
    root = ET.Element('testsuites', {'name': 'manylint'})
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_time = 0.0

    for target_name, hook_results in results_by_target.items():
        target_junit_dir = junit_dir_by_target.get(target_name)
        seen_xunit_files: set[Path] = set()

        for res in hook_results:
            xunit_path = res.xunit_file
            if xunit_path is None and target_junit_dir is not None:
                candidate = target_junit_dir / f'{res.hook_id}.xunit.xml'
                if candidate.is_file():
                    xunit_path = candidate

            if xunit_path is not None and xunit_path.is_file():
                seen_xunit_files.add(xunit_path.resolve())
                try:
                    tree = ET.parse(xunit_path)
                    elem = tree.getroot()
                    suites = [elem] if elem.tag == 'testsuite' else list(elem.findall('testsuite'))
                    for suite in suites:
                        suite.set('name', f'{target_name}.{res.hook_id}')
                        t = int(suite.get('tests', '0'))
                        f = int(suite.get('failures', '0'))
                        e = int(suite.get('errors', '0'))
                        tm = float(suite.get('time', f'{res.duration:.3f}'))
                        total_tests += t
                        total_failures += f
                        total_errors += e
                        total_time += tm
                        root.append(suite)
                    continue
                except ET.ParseError:
                    pass

            # Fallback synthetic testsuite if no xunit XML file was generated
            failures = 1 if res.returncode != 0 else 0
            suite = ET.SubElement(
                root,
                'testsuite',
                {
                    'name': f'{target_name}.{res.hook_id}',
                    'tests': '1',
                    'failures': str(failures),
                    'errors': '0',
                    'time': f'{res.duration:.3f}',
                },
            )
            tc = ET.SubElement(
                suite,
                'testcase',
                {
                    'name': res.hook_id,
                    'classname': f'{target_name}.{res.hook_id}',
                    'time': f'{res.duration:.3f}',
                },
            )
            if res.returncode != 0:
                msg = (res.stdout + '\n' + res.stderr).strip() or f'Exited with code {res.returncode}'
                fail = ET.SubElement(
                    tc,
                    'failure',
                    {'message': f'{res.hook_id} failed (exit code {res.returncode})'},
                )
                fail.text = msg
            total_tests += 1
            total_failures += failures
            total_time += res.duration

        # Also pick up any extra .xunit.xml files written to target_junit_dir (e.g. when pre-commit ran)
        if target_junit_dir is not None and target_junit_dir.is_dir():
            for extra_xml in sorted(target_junit_dir.glob('*.xunit.xml')):
                if extra_xml.resolve() in seen_xunit_files:
                    continue
                seen_xunit_files.add(extra_xml.resolve())
                linter_name = extra_xml.name[: -len('.xunit.xml')]
                try:
                    tree = ET.parse(extra_xml)
                    elem = tree.getroot()
                    suites = [elem] if elem.tag == 'testsuite' else list(elem.findall('testsuite'))
                    for suite in suites:
                        suite.set('name', f'{target_name}.{linter_name}')
                        total_tests += int(suite.get('tests', '0'))
                        total_failures += int(suite.get('failures', '0'))
                        total_errors += int(suite.get('errors', '0'))
                        total_time += float(suite.get('time', '0.0'))
                        root.append(suite)
                except ET.ParseError:
                    pass

    root.set('tests', str(total_tests))
    root.set('failures', str(total_failures))
    root.set('errors', str(total_errors))
    root.set('time', f'{total_time:.3f}')

    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'


def export_junit_directory(
    output_dir: Path,
    results_by_target: dict[str, list[HookResult]],
    junit_dir_by_target: dict[str, Path],
) -> None:
    """Write individual per-target and aggregated JUnit XML files to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for target_name, temp_dir in junit_dir_by_target.items():
        if temp_dir.is_dir():
            for xml_file in sorted(temp_dir.glob('*.xunit.xml')):
                dest = output_dir / f'{target_name}.{xml_file.name}'
                shutil.copy2(xml_file, dest)
    agg_xml = build_aggregated_junit_xml(results_by_target, junit_dir_by_target)
    (output_dir / 'manylint.xunit.xml').write_text(agg_xml, encoding='utf-8')
