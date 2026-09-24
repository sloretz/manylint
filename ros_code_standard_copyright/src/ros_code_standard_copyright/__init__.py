# Copyright 2015 Open Source Robotics Foundation, Inc.
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

from importlib import metadata
import sys


COPYRIGHT_GROUP = 'ament_copyright.copyright_name'
LICENSE_GROUP = 'ament_copyright.license'

SOURCE_FILETYPE = 1
CONTRIBUTING_FILENAME = 'CONTRIBUTING.md'
CONTRIBUTING_FILETYPE = 2
LICENSE_FILENAME = 'LICENSE'
LICENSE_FILETYPE = 3

ALL_FILETYPES = {
    SOURCE_FILETYPE: None,
    CONTRIBUTING_FILETYPE: CONTRIBUTING_FILENAME,
    LICENSE_FILETYPE: LICENSE_FILENAME,
}

UNKNOWN_IDENTIFIER = '<unknown>'


def get_copyright_names():
    from ros_code_standard_copyright import copyright_names as builtin_copyright_names

    names = {
        'osrf': builtin_copyright_names.osrf,
    }
    entry_points = metadata.entry_points()
    for group in (COPYRIGHT_GROUP, 'ros_code_standard_copyright.copyright_name'):
        if sys.version_info >= (3, 12):
            copyright_groups = entry_points.select(group=group)
        else:
            copyright_groups = entry_points.get(group, [])
        for entry_point in copyright_groups:
            assert entry_point.name != UNKNOWN_IDENTIFIER, \
                "Invalid entry point name '%s'" % entry_point.name
            try:
                name = entry_point.load()
                names[entry_point.name] = name
            except Exception:
                pass
    return names


def get_licenses():
    from ros_code_standard_copyright import licenses as builtin_licenses

    licenses = {
        'apache2': builtin_licenses.apache2,
        'boost1': builtin_licenses.boost1,
        'bsd_3clause': builtin_licenses.bsd_3clause,
        'bsd_2clause': builtin_licenses.bsd_2clause,
        'mit': builtin_licenses.mit,
        'mit0': builtin_licenses.mit0,
        'gplv3': builtin_licenses.gplv3,
        'lgplv3': builtin_licenses.lgplv3,
    }
    entry_points = metadata.entry_points()
    for group in (LICENSE_GROUP, 'ros_code_standard_copyright.license'):
        if sys.version_info >= (3, 12):
            license_groups = entry_points.select(group=group)
        else:
            license_groups = entry_points.get(group, [])
        for entry_point in license_groups:
            assert entry_point.name != UNKNOWN_IDENTIFIER, \
                "Invalid entry point name '%s'" % entry_point.name
            try:
                licenses[entry_point.name] = entry_point.load()
            except Exception:
                pass
    return licenses


def get_executable() -> None:
    return None


def run(argv: list[str] | None = None) -> int:
    from ros_code_standard_copyright.cli import main

    if argv is None:
        return main()
    return main(argv)
