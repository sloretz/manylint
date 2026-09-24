#!/usr/bin/env python3

# Copyright 2014-2015 Open Source Robotics Foundation, Inc.
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
from collections import defaultdict
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Literal
from xml.etree import ElementTree
from xml.sax.saxutils import escape
from xml.sax.saxutils import quoteattr

from . import get_executable


def find_cppcheck_executable() -> str | None:
    exe = get_executable()
    if exe.is_file() and os.access(exe, os.X_OK):
        return str(exe)
    return None


def get_cppcheck_version(cppcheck_bin: str) -> str:
    version_cmd = [cppcheck_bin, '--version']
    output = subprocess.check_output(version_cmd)
    output = output.decode().strip()
    tokens = output.split()
    if len(tokens) not in (2, 3):
        raise RuntimeError("unexpected cppcheck version string '{}'".format(output))

    if tokens[0] != 'Cppcheck':
        raise RuntimeError("unexpected cppcheck version name '{}'".format(output))

    return tokens[1]


def main(argv: list[str] | None = None) -> Literal[0, 1]:
    if argv is None:
        argv = sys.argv[1:]

    extensions = ['c', 'cc', 'cpp', 'cxx', 'h', 'hh', 'hpp', 'hxx']

    parser = argparse.ArgumentParser(
        description='Perform static code analysis using cppcheck.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'paths',
        nargs='*',
        default=[os.curdir],
        help='Files and/or directories to be checked. Directories are searched recursively for '
             'files ending in one of %s.' %
             ', '.join(["'.%s'" % e for e in extensions]))
    parser.add_argument(
        '--libraries',
        nargs='*',
        help='Library configurations to load in addition to the standard libraries of C and C++.'
             "Each library is passed to cppcheck as '--library=<library_name>'")
    parser.add_argument(
        '--include_dirs',
        nargs='*',
        help='Include directories for C/C++ files being checked.'
             "Each directory is passed to cppcheck as '-I <include_dir>'")
    parser.add_argument(
        '--exclude',
        nargs='*',
        help='Exclude C/C++ files from being checked.'
             "Each file is passed to cppcheck as '--suppress=*:<file>'")
    parser.add_argument(
        '--language',
        help="Passed to cppcheck as '--language=<language>', and it forces cppcheck to consider "
             "as the given language ('c' or 'c++').")
    parser.add_argument(
        '--xunit-file',
        help='Generate a xunit compliant XML file')
    parser.add_argument(
        '--cppcheck-version',
        action='store_true',
        help='Get the cppcheck version, print it, and then exit.')
    args = parser.parse_args(argv)

    if not args.xunit_file and os.environ.get('MANYLINT_JUNIT_DIR'):
        args.xunit_file = os.path.join(os.environ['MANYLINT_JUNIT_DIR'], 'cppcheck.xunit.xml')

    cppcheck_bin = find_cppcheck_executable()
    if not cppcheck_bin:
        print("Could not find bundled 'cppcheck' executable", file=sys.stderr)
        return 1

    cppcheck_version = get_cppcheck_version(cppcheck_bin)

    if args.cppcheck_version:
        print(cppcheck_version)
        return 0

    if args.xunit_file:
        start_time = time.time()

    files = get_files(args.paths, extensions)
    if not files:
        print('No files found', file=sys.stderr)
        if args.xunit_file:
            write_xunit_file(args.xunit_file, {}, time.time() - start_time)
        return 0

    # try to determine the number of CPU cores
    jobs = None
    try:
        jobs = multiprocessing.cpu_count()
    except NotImplementedError:
        # the number of cores cannot be determined, do not extend args
        pass

    cfg_dir = Path(cppcheck_bin).resolve().parent / 'cfg'
    std_cfg = cfg_dir / 'std.cfg'

    # invoke cppcheck
    cmd = [cppcheck_bin,
           '-f',
           '--inline-suppr',
           '-q',
           '-rp',
           '--xml',
           '--xml-version=2',
           '--suppress=internalAstError',
           '--suppress=unknownMacro']
    if std_cfg.is_file():
        cmd.append(f'--library={std_cfg}')
    if args.language:
        cmd.extend(['--language={0}'.format(args.language)])
    for library in (args.libraries or []):
        bundled_lib = cfg_dir / (library if library.endswith('.cfg') else f'{library}.cfg')
        if bundled_lib.is_file():
            cmd.extend([f'--library={bundled_lib}'])
        else:
            cmd.extend(['--library={0}'.format(library)])
    for include_dir in (args.include_dirs or []):
        cmd.extend(['-I', include_dir])
    for exclude in (args.exclude or []):
        cmd.extend(['--suppress=*:' + exclude])
    if jobs:
        cmd.extend(['-j', '%d' % jobs])
    cmd.extend(files)
    try:
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        xml = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("The invocation of 'cppcheck' failed with error code %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as e:
        print('Invalid XML in cppcheck output: %s' % str(e),
              file=sys.stderr)
        return 1

    # output errors
    report = defaultdict(list)
    # even though we use a defaultdict, explicitly add known files so they are listed
    for filename in files:
        report[filename] = []
    errors_elem = root.find('errors')
    if errors_elem is not None:
        for error in errors_elem:
            location = error.find('location')
            if location is None:
                continue
            filename = location.get('file')
            if not filename:
                continue
            data = {
                'line': int(location.get('line', 0)),
                'id': error.get('id'),
                'severity': error.get('severity'),
                'msg': error.get('verbose'),
            }
            for key in report.keys():
                if os.path.exists(filename) and os.path.exists(key) and os.path.samefile(key, filename):
                    filename = key
                    break
            # in the case where relative and absolute paths are mixed for paths and
            # include_dirs cppcheck might return duplicate results
            if data not in report[filename]:
                report[filename].append(data)

                data = dict(data)
                data['filename'] = filename
                print('[%(filename)s:%(line)d]: (%(severity)s: %(id)s) %(msg)s' % data,
                      file=sys.stderr)

    # output summary
    error_count = sum(len(r) for r in report.values())
    if not error_count:
        print('No problems found')
        rc = 0
    else:
        print('%d errors' % error_count, file=sys.stderr)
        rc = 1

    # generate xunit file
    if args.xunit_file:
        write_xunit_file(args.xunit_file, report, time.time() - start_time)

    return rc


def get_files(paths, extensions):
    files = []
    for path in paths:
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                if 'AMENT_IGNORE' in dirnames + filenames or 'COLCON_IGNORE' in dirnames + filenames:
                    dirnames[:] = []
                    continue
                # ignore folder starting with . or _
                dirnames[:] = [d for d in dirnames if d[0] not in ['.', '_']]
                dirnames.sort()

                # select files by extension
                for filename in sorted(filenames):
                    _, ext = os.path.splitext(filename)
                    if ext in ['.%s' % e for e in extensions]:
                        files.append(os.path.join(dirpath, filename))
        if os.path.isfile(path):
            files.append(path)
    return [os.path.normpath(f) for f in files]


def get_xunit_content(report, testname, elapsed, skip=None):
    test_count = sum(max(len(r), 1) for r in report.values())
    error_count = sum(len(r) for r in report.values())
    data = {
        'testname': testname,
        'test_count': test_count,
        'error_count': error_count,
        'time': '%.3f' % round(elapsed, 3),
        'skip': test_count if skip else 0,
    }
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite
  name="%(testname)s"
  tests="%(test_count)d"
  errors="0"
  failures="%(error_count)d"
  time="%(time)s"
  skipped="%(skip)d"
>
""" % data

    for filename in sorted(report.keys()):
        errors = report[filename]

        if skip:
            data = {
                'quoted_name': quoteattr(filename),
                'testname': testname,
                'quoted_message': quoteattr(''),
                'skip': skip,
            }
            xml += """  <testcase
    name=%(quoted_name)s
    classname="%(testname)s"
  >
    <skipped type="skip" message=%(quoted_message)s>
      ![CDATA[Test Skipped due to %(skip)s]]
    </skipped>
  </testcase>
""" % data
        elif errors:
            # report each cppcheck error as a failing testcase
            for error in errors:
                data = {
                    'quoted_name': quoteattr(
                        '%s: %s (%s:%d)' % (
                            error['severity'], error['id'],
                            filename, error['line'])),
                    'testname': testname,
                    'quoted_message': quoteattr(error['msg']),
                }
                xml += """  <testcase
    name=%(quoted_name)s
    classname="%(testname)s"
  >
      <failure message=%(quoted_message)s/>
  </testcase>
""" % data

        else:
            # if there are no cppcheck errors report a single successful test
            data = {
                'quoted_location': quoteattr(filename),
                'testname': testname,
            }
            xml += """  <testcase
    name=%(quoted_location)s
    classname="%(testname)s"/>
""" % data

    # output list of checked files
    if skip:
        data = {
            'skip': skip,
        }
        xml += """  <system-err>Tests Skipped due to %(skip)s</system-err>
""" % data
    else:
        data = {
            'escaped_files': escape(
                ''.join(['\n* %s' % r for r in sorted(report.keys())])
            ),
        }
        xml += """  <system-out>Checked files:%(escaped_files)s</system-out>
""" % data

    xml += '</testsuite>\n'
    return xml


def write_xunit_file(xunit_file, report, duration, skip=None):
    folder_name = os.path.basename(os.path.dirname(xunit_file))
    file_name = os.path.basename(xunit_file)
    suffix = '.xml'
    if file_name.endswith(suffix):
        file_name = file_name[0:-len(suffix)]
        suffix = '.xunit'
        if file_name.endswith(suffix):
            file_name = file_name[0:-len(suffix)]
    testname = '%s.%s' % (folder_name, file_name)

    xml = get_xunit_content(report, testname, duration, skip)
    path = os.path.dirname(os.path.abspath(xunit_file))
    if not os.path.exists(path):
        os.makedirs(path)
    with open(xunit_file, 'w') as f:
        f.write(xml)


if __name__ == '__main__':
    sys.exit(main())
