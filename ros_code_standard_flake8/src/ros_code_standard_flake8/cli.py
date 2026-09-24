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

from pathlib import Path
import subprocess
import sys

DEFAULT_CONFIG = Path(__file__).resolve().parent / 'configuration' / 'ament_flake8.ini'


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    has_config = any(a == '--config' or a.startswith('--config=') for a in args)
    cmd = [sys.executable, '-m', 'flake8']
    if not has_config:
        cmd.append(f'--config={DEFAULT_CONFIG}')
    cmd.extend(args or ['.'])
    return subprocess.run(cmd, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
