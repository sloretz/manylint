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
import re
import sys

from lxml import etree

SCHEMA_DIR = Path(__file__).resolve().parent / 'schemas'
XML_EXTS = {'.xml', '.launch', '.sdf', '.urdf', '.xacro'}
MODEL_PI_ATTR_RE = re.compile(r'(\w+)\s*=\s*["\']([^"\']+)["\']')


def _resolve_schema(href: str, xml_file: Path) -> Path | None:
    basename = href.rsplit('/', 1)[-1]
    bundled = SCHEMA_DIR / basename
    if bundled.is_file():
        return bundled
    local = (xml_file.parent / href).resolve()
    return local if local.is_file() else None


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
                    if fp.suffix in XML_EXTS:
                        out.append(fp)
    return out


def _validate_file(xml_path: Path, xsd_cache: dict[Path, etree.XMLSchema]) -> list[str]:
    errors: list[str] = []
    try:
        doc = etree.parse(str(xml_path))
    except etree.XMLSyntaxError as exc:
        return [f'{xml_path}:{exc.lineno or 1}: XML syntax error: {exc.msg}']

    root = doc.getroot()
    pi = root.getprevious()
    while pi is not None:
        if isinstance(pi, etree._ProcessingInstruction) and pi.target == 'xml-model':
            attrs = dict(MODEL_PI_ATTR_RE.findall(pi.text or ''))
            href = attrs.get('href', '')
            if href.endswith('.xsd'):
                schema_path = _resolve_schema(href, xml_path)
                if schema_path is not None:
                    if schema_path not in xsd_cache:
                        xsd_cache[schema_path] = etree.XMLSchema(etree.parse(str(schema_path)))
                    schema = xsd_cache[schema_path]
                    if not schema.validate(doc):
                        for err in schema.error_log:
                            errors.append(f'{xml_path}:{err.line}: {err.message}')
        pi = pi.getprevious()
    return errors


def main(argv: list[str] | None = None) -> int:
    files = _expand(list(sys.argv[1:] if argv is None else argv))
    xsd_cache: dict[Path, etree.XMLSchema] = {}
    all_errors: list[str] = []
    for fp in files:
        all_errors.extend(_validate_file(fp, xsd_cache))
    for err in all_errors:
        print(err, file=sys.stderr)
    return 1 if all_errors else 0


if __name__ == '__main__':
    sys.exit(main())
