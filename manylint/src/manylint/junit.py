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

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
import xml.etree.ElementTree as ET


@dataclass
class HookResult:
    """Represents the result of running a single pre-commit or manylint hook on a target."""

    target_name: str
    target_root: Path
    hook_id: str
    returncode: int
    duration: float
    stdout: str
    stderr: str
    matched_files: list[Path] = field(default_factory=list)
    modified_files: list[Path] = field(default_factory=list)


_DIAG_LINE_RE = re.compile(r'^([^:\n]+):(\d+)(?::\d+)?:\s*(.+)$')


def _rel_display(fp: Path, target_name: str, target_root: Path) -> str:
    try:
        return f'{target_name}/{fp.relative_to(target_root)}'
    except ValueError:
        return fp.name


def _parse_diagnostics_by_file(
    output: str,
    matched_files: list[Path],
    target_root: Path,
) -> dict[Path, list[str]]:
    by_path: dict[Path, list[str]] = defaultdict(list)
    lookup: dict[str, Path] = {}
    for fp in matched_files:
        lookup[str(fp)] = fp
        lookup[fp.name] = fp
        try:
            lookup[str(fp.relative_to(target_root))] = fp
        except ValueError:
            pass

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _DIAG_LINE_RE.match(line)
        if m:
            candidate_str = m.group(1).strip()
            fp = lookup.get(candidate_str)
            if fp is None:
                resolved = (target_root / candidate_str).resolve()
                if resolved in lookup.values():
                    fp = resolved
            if fp is not None:
                by_path[fp].append(line)
    return by_path


def _build_suite_element(res: HookResult) -> tuple[ET.Element, int, int]:
    suite_name = f'{res.target_name}.{res.hook_id}'
    combined_out = (res.stdout + '\n' + res.stderr).strip()
    diags_by_file = _parse_diagnostics_by_file(combined_out, res.matched_files, res.target_root)
    mod_set = set(res.modified_files)

    files = sorted(res.matched_files)
    suite = ET.Element('testsuite', {'name': suite_name})
    tests = 0
    failures = 0

    for fp in files:
        rel_name = _rel_display(fp, res.target_name, res.target_root)
        file_diags = diags_by_file.get(fp, [])
        is_mod = fp in mod_set

        if is_mod or file_diags:
            tests += 1
            failures += 1
            tc = ET.SubElement(suite, 'testcase', {'name': rel_name, 'classname': suite_name})
            msg = (
                f'Reformatted {rel_name} in-place'
                if is_mod
                else file_diags[0]
            )
            fail = ET.SubElement(tc, 'failure', {'message': msg})
            fail.text = '\n'.join(file_diags) if file_diags else combined_out or msg
        else:
            tests += 1
            ET.SubElement(suite, 'testcase', {'name': rel_name, 'classname': suite_name})

    # If the hook failed overall but no specific file matched a diagnostic line or modification
    if res.returncode != 0 and failures == 0:
        tests += 1
        failures += 1
        tc = ET.SubElement(suite, 'testcase', {'name': res.hook_id, 'classname': suite_name})
        fail = ET.SubElement(
            tc,
            'failure',
            {'message': f'{res.hook_id} failed (exit code {res.returncode})'},
        )
        fail.text = combined_out or f'Exited with code {res.returncode}'

    if files:
        sys_out = ET.SubElement(suite, 'system-out')
        checked_list = '\n'.join(
            f'* {_rel_display(fp, res.target_name, res.target_root)}' for fp in files
        )
        sys_out.text = f'Checked files:\n{checked_list}'

    suite.set('tests', str(tests))
    suite.set('errors', '0')
    suite.set('failures', str(failures))
    suite.set('time', f'{res.duration:.3f}')
    return suite, tests, failures


def build_aggregated_junit_xml(results_by_target: dict[str, list[HookResult]]) -> str:
    """Build aggregated JUnit XML directly from HookResults without per-linter XML boilerplate."""
    root = ET.Element('testsuites', {'name': 'manylint'})
    total_tests = 0
    total_failures = 0
    total_time = 0.0

    for hook_results in results_by_target.values():
        for res in hook_results:
            suite, tests, failures = _build_suite_element(res)
            total_tests += tests
            total_failures += failures
            total_time += res.duration
            root.append(suite)

    root.set('tests', str(total_tests))
    root.set('failures', str(total_failures))
    root.set('errors', '0')
    root.set('time', f'{total_time:.3f}')

    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'


def export_junit_directory(
    output_dir: Path,
    results_by_target: dict[str, list[HookResult]],
) -> None:
    """Write per-target/per-hook and aggregated JUnit XML files to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for target_name, hook_results in results_by_target.items():
        for res in hook_results:
            suite, _, _ = _build_suite_element(res)
            ET.indent(suite, space='  ')
            xml_text = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                + ET.tostring(suite, encoding='unicode')
                + '\n'
            )
            (output_dir / f'{target_name}.{res.hook_id}.xunit.xml').write_text(
                xml_text, encoding='utf-8'
            )
    agg_xml = build_aggregated_junit_xml(results_by_target)
    (output_dir / 'manylint.xunit.xml').write_text(agg_xml, encoding='utf-8')
