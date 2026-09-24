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

import sys

from ros_code_standard_copyright import (
    SOURCE_FILETYPE,
    UNKNOWN_IDENTIFIER,
    get_copyright_names,
    get_licenses,
)
from ros_code_standard_copyright.crawler import get_files
from ros_code_standard_copyright.parser import parse_file

DEFAULT_EXTS = ['c', 'cc', 'cpp', 'cxx', 'h', 'hh', 'hpp', 'hxx', 'py', 'cmake']


def main(argv: list[str] | None = None) -> int:
    paths = list(sys.argv[1:] if argv is None else argv) or ['.']
    filenames = get_files(paths, DEFAULT_EXTS, [])
    if not filenames:
        return 0

    names = get_copyright_names()
    licenses = get_licenses()

    errors: list[str] = []
    for filename in sorted(filenames):
        desc = parse_file(filename, licenses, names)
        if desc.filetype != SOURCE_FILETYPE or not desc.exists or not desc.content:
            continue
        if not desc.copyright_identifiers:
            errors.append(f'{desc.path}:1: could not find copyright notice')
        elif desc.license_identifier == UNKNOWN_IDENTIFIER:
            errors.append(f'{desc.path}:1: could not find recognized license header')

    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
