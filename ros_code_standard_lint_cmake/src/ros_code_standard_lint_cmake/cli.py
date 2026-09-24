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
                    if f == 'CMakeLists.txt' or f.endswith('.cmake'):
                        out.append(str(Path(root) / f))
    return out


def main(argv: list[str] | None = None) -> int:
    files = _expand(list(sys.argv[1:] if argv is None else argv))
    if not files:
        return 0
    cmd = [sys.executable, '-m', 'cmakelint.main', '--filter=', *files]
    return subprocess.run(cmd, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
