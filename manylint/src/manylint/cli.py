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

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
import yaml

from manylint.discovery import LintTarget, collect_target_files, discover_targets
from manylint.junit import HookResult, build_aggregated_junit_xml, export_junit_directory

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / 'data' / 'default_pre_commit_config.yaml'


def _hash_files(files: list[Path]) -> dict[Path, bytes]:
    digests: dict[Path, bytes] = {}
    for fp in files:
        try:
            digests[fp] = hashlib.sha256(fp.read_bytes()).digest()
        except OSError:
            pass
    return digests


def _match_hook_files(hook: dict, files: list[Path], target_root: Path) -> list[Path]:
    files_regex = hook.get('files')
    exclude_regex = hook.get('exclude')
    types = hook.get('types', [])

    file_pat = re.compile(files_regex) if files_regex else None
    excl_pat = re.compile(exclude_regex) if exclude_regex else None

    matched: list[Path] = []
    for fp in files:
        try:
            rel = str(fp.relative_to(target_root))
        except ValueError:
            rel = fp.name

        if excl_pat and excl_pat.search(rel):
            continue

        if 'python' in types and fp.suffix != '.py':
            continue
        if file_pat and not file_pat.search(rel):
            continue

        matched.append(fp)
    return matched


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    venv_bin = str(Path(sys.prefix) / 'bin')
    current_path = env.get('PATH', '')
    if venv_bin not in current_path.split(os.pathsep):
        env['PATH'] = f'{venv_bin}{os.pathsep}{current_path}' if current_path else venv_bin
    env.setdefault('PRE_COMMIT_HOME', '/tmp/manylint-pre-commit-cache')
    return env


def _run_target_hooks(
    target: LintTarget,
    target_files: list[Path],
    selected_linters: set[str] | None,
    use_pre_commit_cli: bool,
) -> tuple[str, Path, list[HookResult], dict[str, list[Path]]]:
    config_path = target.custom_config if target.custom_config is not None else DEFAULT_CONFIG_PATH
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}

    results: list[HookResult] = []
    modified_by_hook: dict[str, list[Path]] = {}
    env = _build_env()
    pre_commit_bin = shutil.which('pre-commit', path=env['PATH'])

    for repo_entry in cfg.get('repos', []):
        repo_url = repo_entry.get('repo', 'local')
        for hook in repo_entry.get('hooks', []):
            hook_id = hook.get('id', '')
            if not hook_id:
                continue
            if selected_linters is not None and hook_id not in selected_linters:
                continue

            matched_files = _match_hook_files(hook, target_files, target.root)
            if not matched_files:
                continue

            before_hashes = _hash_files(matched_files)
            t0 = time.monotonic()

            can_run_direct = (
                repo_url == 'local'
                and hook.get('language') in ('system', 'python', None)
                and not use_pre_commit_cli
                and target.custom_config is None
            )

            if can_run_direct or target.git_root is None or pre_commit_bin is None:
                entry_cmd = shlex.split(hook.get('entry', hook_id))
                resolved_exe = shutil.which(entry_cmd[0], path=env['PATH'])
                if resolved_exe:
                    entry_cmd[0] = resolved_exe
                hook_args = [str(a) for a in hook.get('args', [])]
                cmd = entry_cmd + hook_args + [str(fp) for fp in matched_files]
                cwd = target.root
            else:
                cmd = [
                    pre_commit_bin,
                    'run',
                    hook_id,
                    '--config',
                    str(config_path),
                    '--files',
                    *[str(fp) for fp in matched_files],
                ]
                cwd = target.git_root

            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            duration = time.monotonic() - t0

            after_hashes = _hash_files(matched_files)
            modified_files = [
                fp for fp, digest in before_hashes.items() if after_hashes.get(fp) != digest
            ]
            if modified_files:
                modified_by_hook[hook_id] = modified_files

            rc = proc.returncode
            if modified_files and rc == 0:
                rc = 1

            results.append(
                HookResult(
                    target_name=target.name,
                    target_root=target.root,
                    hook_id=hook_id,
                    returncode=rc,
                    duration=duration,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    matched_files=matched_files,
                    modified_files=modified_files,
                )
            )

    return target.name, config_path, results, modified_by_hook


def _print_text_report(
    targets: list[LintTarget],
    config_by_target: dict[str, Path],
    results_by_target: dict[str, list[HookResult]],
    modified_by_target: dict[str, dict[str, list[Path]]],
) -> None:
    total_targets = len(targets)
    failed_targets = 0
    total_hooks = 0
    failed_hooks = 0

    for target in targets:
        tname = target.name
        cfg_path = config_by_target.get(tname, DEFAULT_CONFIG_PATH)
        cfg_label = (
            f'custom ({cfg_path})'
            if target.custom_config is not None
            else 'default (ros_code_standard)'
        )
        print(f'==> {tname} ({target.root}) [{cfg_label}]')
        hook_results = results_by_target.get(tname, [])
        if not hook_results:
            print('  - (no matching files for configured linters)')
            continue

        target_failed = False
        for res in hook_results:
            total_hooks += 1
            mod_files = modified_by_target.get(tname, {}).get(res.hook_id, [])
            if res.returncode == 0:
                print(f'  ✓ {res.hook_id:<14} ({res.duration:.2f}s)')
            else:
                failed_hooks += 1
                target_failed = True
                if mod_files:
                    print(
                        f'  ✗ {res.hook_id:<14} ({res.duration:.2f}s) '
                        f'[reformatted {len(mod_files)} file(s) in-place]'
                    )
                else:
                    print(f'  ✗ {res.hook_id:<14} ({res.duration:.2f}s)')
                output = (res.stdout + '\n' + res.stderr).strip()
                if output:
                    for line in output.splitlines()[:25]:
                        print(f'      {line}')
        if target_failed:
            failed_targets += 1

    print(
        f'\nSummary: {total_targets - failed_targets}/{total_targets} targets passed, '
        f'{total_hooks - failed_hooks}/{total_hooks} linter runs passed.'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='manylint',
        description='Run pinned ROS 2 linters and pre-commit configurations across repositories.',
    )
    parser.add_argument(
        'paths',
        nargs='*',
        default=['.'],
        help='Files, ROS packages, or workspace directories to lint (default: current directory).',
    )
    parser.add_argument(
        '--output',
        choices=('text', 'junit'),
        default='text',
        help='Output format for stdout: human-readable text or JUnit XML (default: text).',
    )
    parser.add_argument(
        '--junit-file',
        type=Path,
        default=None,
        help='Write an aggregated JUnit XML report to this file path.',
    )
    parser.add_argument(
        '--junit-dir',
        type=Path,
        default=None,
        help='Write per-target and aggregated JUnit XML files to this directory.',
    )
    parser.add_argument(
        '--linters',
        type=str,
        default=None,
        help='Comma-separated list of linter hook IDs to run (e.g., uncrustify,flake8).',
    )
    parser.add_argument(
        '--git-diff',
        nargs='?',
        const='origin/main',
        default=None,
        metavar='REF',
        help='Only lint files changed since REF (default: origin/main).',
    )
    parser.add_argument(
        '--git-staged',
        action='store_true',
        help='Only lint files staged in the Git index.',
    )
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        help='Glob pattern of files to exclude (can be passed multiple times).',
    )
    parser.add_argument(
        '-j',
        '--jobs',
        type=int,
        default=os.cpu_count() or 4,
        help='Number of parallel targets to lint concurrently.',
    )
    parser.add_argument(
        '--use-pre-commit',
        action='store_true',
        help='Force invoking the pre-commit CLI even for the default local configuration.',
    )

    args = parser.parse_args(argv)

    selected_linters: set[str] | None = None
    if args.linters:
        selected_linters = {item.strip() for item in args.linters.split(',') if item.strip()}

    exclude_patterns: list[str] = []
    for item in args.exclude:
        exclude_patterns.extend(p.strip() for p in item.split(',') if p.strip())

    targets = discover_targets(args.paths)

    seen_names: set[str] = set()
    files_by_target: dict[str, list[Path]] = {}
    for idx, target in enumerate(targets):
        if target.name in seen_names:
            target.name = f'{target.name}_{idx}'
        seen_names.add(target.name)
        files_by_target[target.name] = collect_target_files(
            target,
            exclude_patterns=exclude_patterns,
            git_diff_ref=args.git_diff,
            git_staged=args.git_staged,
        )

    results_by_target: dict[str, list[HookResult]] = {}
    config_by_target: dict[str, Path] = {}
    modified_by_target: dict[str, dict[str, list[Path]]] = {}

    max_workers = max(1, min(args.jobs, len(targets) or 1))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(
                _run_target_hooks,
                target,
                files_by_target[target.name],
                selected_linters,
                args.use_pre_commit,
            )
            for target in targets
        ]
        for fut in futures:
            tname, cfg_path, hook_results, mod_map = fut.result()
            config_by_target[tname] = cfg_path
            results_by_target[tname] = hook_results
            modified_by_target[tname] = mod_map

    if args.junit_file is not None:
        args.junit_file.parent.mkdir(parents=True, exist_ok=True)
        xml_str = build_aggregated_junit_xml(results_by_target)
        args.junit_file.write_text(xml_str, encoding='utf-8')

    if args.junit_dir is not None:
        export_junit_directory(args.junit_dir, results_by_target)

    if args.output == 'junit':
        sys.stdout.write(build_aggregated_junit_xml(results_by_target))
    else:
        _print_text_report(targets, config_by_target, results_by_target, modified_by_target)

    any_failed = any(
        res.returncode != 0
        for hook_list in results_by_target.values()
        for res in hook_list
    )
    return 1 if any_failed else 0


if __name__ == '__main__':
    sys.exit(main())
