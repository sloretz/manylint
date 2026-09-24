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

import os
from pathlib import Path
import subprocess
import sys

PACKAGE_DIR = Path(__file__).resolve().parent
STD_CFG = PACKAGE_DIR / 'bin' / 'cfg' / 'std.cfg'
CPP_EXTS = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx'}


def get_executable() -> Path:
    return PACKAGE_DIR / 'bin' / 'cppcheck'


def _expand(paths: list[str]) -> list[str]:
    out: list[str] = []
    for raw in paths or ['.']:
        p = Path(raw)
        if p.is_file():
            out.append(str(p))
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                if 'AMENT_IGNORE' in files or 'COLCON_IGNORE' in files:
                    dirs[:] = []
                    continue
                dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
                for f in sorted(files):
                    fp = Path(root) / f
                    if fp.suffix in CPP_EXTS:
                        out.append(str(fp))
    return out


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    files = _expand(raw_args)
    if not files:
        return 0

    cmd = [
        str(get_executable()),
        '-f',
        '--inline-suppr',
        '-q',
        '--error-exitcode=1',
        f'--library={STD_CFG}',
        '--suppress=internalAstError',
        '--suppress=unknownMacro',
        '--template={file}:{line}: [{severity}:{id}] {message}',
        *files,
    ]
    return subprocess.run(cmd, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
