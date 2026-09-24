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

import hashlib
import os
from pathlib import Path
import subprocess
import sys

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_CFG = PACKAGE_DIR / 'configuration' / 'ament_code_style_0_78.cfg'
CPP_EXTS = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx'}


def get_executable() -> Path:
    return PACKAGE_DIR / 'bin' / 'uncrustify'


def _expand(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths or ['.']:
        p = Path(raw)
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                if 'AMENT_IGNORE' in files or 'COLCON_IGNORE' in files:
                    dirs[:] = []
                    continue
                dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
                for f in sorted(files):
                    fp = Path(root) / f
                    if fp.suffix in CPP_EXTS:
                        out.append(fp)
    return out


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    check_only = '--check' in raw_args or '--no-reformat' in raw_args
    paths = [a for a in raw_args if a not in ('--check', '--no-reformat', '--reformat')]

    files = _expand(paths)
    if not files:
        return 0

    before = {fp: hashlib.sha256(fp.read_bytes()).digest() for fp in files}
    mode_args = ['--check'] if check_only else ['--replace', '--no-backup']
    cmd = [str(get_executable()), '-c', str(DEFAULT_CFG), '-q', *mode_args, *(str(f) for f in files)]
    proc = subprocess.run(cmd, check=False)

    modified = [fp for fp in files if hashlib.sha256(fp.read_bytes()).digest() != before[fp]]
    for fp in modified:
        print(f"Code style divergence in file '{fp}': reformatted file")
    return 1 if (proc.returncode != 0 or modified) else 0


if __name__ == '__main__':
    sys.exit(main())
