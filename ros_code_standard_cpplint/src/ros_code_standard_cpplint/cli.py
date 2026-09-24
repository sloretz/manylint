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
import os
from pathlib import Path
import re
import sys

import cpplint

CPP_EXTS = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx'}
ROS2_FILTERS = (
    '-build/c++11,-runtime/references,-whitespace/braces,'
    '-whitespace/indent,-whitespace/parens,-whitespace/semicolon'
)


def _ros_header_guard(filename: str) -> str:
    fileinfo = cpplint.FileInfo(filename)
    path = fileinfo.RepositoryName()
    if cpplint._root:
        prefix = cpplint._root.replace(os.sep, '/') + '/'
        fn_norm = filename.replace(os.sep, '/')
        if path.startswith(prefix):
            path = path[len(prefix) :]
        elif fn_norm.startswith(prefix):
            path = fn_norm[len(prefix) :]
    path = path.replace('/', '//')
    return re.sub(r'[^a-zA-Z0-9]', '_', path).upper() + '_'


cpplint.GetHeaderGuardCPPVariable = _ros_header_guard


def _find_root(filepath: Path) -> str:
    for parent in filepath.resolve().parents:
        if parent.name in ('include', 'src', 'test'):
            return str(parent)
    return str(filepath.resolve().parent)


def _expand(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths or ['.']:
        p = Path(raw)
        if p.is_file():
            out.append(p.resolve())
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                if 'AMENT_IGNORE' in files or 'COLCON_IGNORE' in files:
                    dirs[:] = []
                    continue
                dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
                for f in sorted(files):
                    fp = (Path(root) / f).resolve()
                    if fp.suffix in CPP_EXTS:
                        out.append(fp)
    return out


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    files = _expand(raw_args)
    if not files:
        return 0

    by_root: dict[str, list[str]] = defaultdict(list)
    for fp in files:
        by_root[_find_root(fp)].append(str(fp))

    cpplint._cpplint_state.ResetErrorCounts()
    for root_dir, group_files in sorted(by_root.items()):
        filenames = cpplint.ParseArguments(
            [
                '--counting=detailed',
                '--linelength=100',
                f'--filter={ROS2_FILTERS}',
                f'--root={root_dir}',
                *group_files,
            ]
        )
        for fn in filenames:
            cpplint.ProcessFile(fn, cpplint._cpplint_state.verbose_level)

    return 1 if cpplint._cpplint_state.error_count else 0


if __name__ == '__main__':
    sys.exit(main())
