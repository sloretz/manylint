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

import subprocess
import sys

ROS2_PEP257_IGNORE = 'D100,D101,D102,D103,D104,D105,D106,D107,D203,D212,D404'


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = [
        sys.executable,
        '-m',
        'pydocstyle',
        '--convention=pep257',
        f'--add-ignore={ROS2_PEP257_IGNORE}',
        *(args or ['.']),
    ]
    return subprocess.run(cmd, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
