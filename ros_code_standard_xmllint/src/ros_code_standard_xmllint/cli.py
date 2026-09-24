#!/usr/bin/env python3
"""CLI implementation for ros-code-standard-xmllint using lxml.etree and bundled ROS XSD schemas."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Literal
import urllib.request
from xml.etree import ElementTree
from xml.sax import make_parser
from xml.sax import SAXParseException
from xml.sax.handler import ContentHandler, feature_external_ges, feature_external_pes
from xml.sax.saxutils import escape, quoteattr

import lxml.etree
try:
    import lxml.isoschematron as _isoschematron
except ImportError:
    _isoschematron = None


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

BUNDLED_SCHEMA_MAP: dict[str, Path] = {
    "http://download.ros.org/schema/package_format1.xsd": SCHEMAS_DIR / "package_format1.xsd",
    "https://download.ros.org/schema/package_format1.xsd": SCHEMAS_DIR / "package_format1.xsd",
    "package_format1.xsd": SCHEMAS_DIR / "package_format1.xsd",
    "http://download.ros.org/schema/package_format2.xsd": SCHEMAS_DIR / "package_format2.xsd",
    "https://download.ros.org/schema/package_format2.xsd": SCHEMAS_DIR / "package_format2.xsd",
    "package_format2.xsd": SCHEMAS_DIR / "package_format2.xsd",
    "http://download.ros.org/schema/package_format3.xsd": SCHEMAS_DIR / "package_format3.xsd",
    "https://download.ros.org/schema/package_format3.xsd": SCHEMAS_DIR / "package_format3.xsd",
    "package_format3.xsd": SCHEMAS_DIR / "package_format3.xsd",
    "https://raw.githubusercontent.com/eclipse-cyclonedds/cyclonedds/master/etc/cyclonedds.xsd": (
        SCHEMAS_DIR / "cyclonedds.xsd"
    ),
    "http://www.omg.org/spec/DDS-SECURITY/20170901/omg_shared_ca_governance.xsd": (
        SCHEMAS_DIR / "omg_shared_ca_governance.xsd"
    ),
    "https://www.omg.org/spec/DDS-SECURITY/20170901/omg_shared_ca_governance.xsd": (
        SCHEMAS_DIR / "omg_shared_ca_governance.xsd"
    ),
    "http://www.omg.org/spec/DDS-SECURITY/20170901/omg_shared_ca_permissions.xsd": (
        SCHEMAS_DIR / "omg_shared_ca_permissions.xsd"
    ),
    "https://www.omg.org/spec/DDS-SECURITY/20170901/omg_shared_ca_permissions.xsd": (
        SCHEMAS_DIR / "omg_shared_ca_permissions.xsd"
    ),
    "http://www.omg.org/spec/DDS-Security/20170801/omg_shared_ca_permissions.xsd": (
        SCHEMAS_DIR / "omg_shared_ca_permissions.xsd"
    ),
    "http://www.omg.org/spec/DDS-*20170801/omg_shared_ca_permissions.xsd": (
        SCHEMAS_DIR / "omg_shared_ca_permissions.xsd"
    ),
}

_VALIDATOR_CACHE: dict[tuple[str, str], Any] = {}


def get_schemas_dir() -> Path:
    """Return the path to the bundled schemas directory."""
    return SCHEMAS_DIR


def get_local_schema_path(
    path: str,
    temp_dir: str,
    xml_file_dir: str | None = None,
) -> str:
    """Resolve a schema URL or path to a local filesystem path, preferring bundled schemas."""
    if path in BUNDLED_SCHEMA_MAP and BUNDLED_SCHEMA_MAP[path].is_file():
        return str(BUNDLED_SCHEMA_MAP[path])

    if not path.startswith(("http://", "https://")):
        if os.path.isabs(path) and os.path.exists(path):
            return path
        if xml_file_dir:
            rel_candidate = os.path.normpath(os.path.join(xml_file_dir, path))
            if os.path.exists(rel_candidate):
                return rel_candidate
        if os.path.exists(path):
            return os.path.abspath(path)
        basename = os.path.basename(path)
        if basename in BUNDLED_SCHEMA_MAP and BUNDLED_SCHEMA_MAP[basename].is_file():
            return str(BUNDLED_SCHEMA_MAP[basename])
        if xml_file_dir:
            return os.path.normpath(os.path.join(xml_file_dir, path))
        return path

    basename = os.path.basename(path)
    if basename in BUNDLED_SCHEMA_MAP and BUNDLED_SCHEMA_MAP[basename].is_file():
        return str(BUNDLED_SCHEMA_MAP[basename])

    url_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()
    _, ext = os.path.splitext(path)
    if ext not in [".xsd", ".rng", ".sch"]:
        ext = ""
    local_path = os.path.join(temp_dir, url_hash + ext)

    if not os.path.exists(local_path):
        try:
            with urllib.request.urlopen(path, timeout=10) as response, open(
                local_path, "wb"
            ) as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Warning: failed to download schema from '{path}': {e}", file=sys.stderr)
            return path
    return local_path


class CustomHandler(ContentHandler):
    """SAX ContentHandler that extracts <?xml-model ...?> and root element attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.xml_model_attributes: list[dict[str, str]] = []
        self.root_attributes: dict[str, str] = {}
        self._first_node = False

    def processingInstruction(self, target: str, data: str) -> None:
        if target != "xml-model":
            return
        try:
            root = ElementTree.fromstring("<data " + data + "/>")
            self.xml_model_attributes.append(dict(root.attrib))
        except Exception:
            pass

    def startDocument(self) -> None:
        self._first_node = True

    def startElement(self, name: str, attrs: Any) -> None:
        if not self._first_node:
            return
        self._first_node = False
        for attr_name in attrs.getNames():
            self.root_attributes[attr_name] = attrs.getValue(attr_name)


def _extract_validation_specs(
    filename: str,
    doc: lxml.etree._ElementTree,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Extract xml-model processing instructions and root attributes from an XML file."""
    handler = CustomHandler()
    try:
        sax_parser = make_parser()
        try:
            sax_parser.setFeature(feature_external_ges, False)
            sax_parser.setFeature(feature_external_pes, False)
        except Exception:
            pass
        sax_parser.setContentHandler(handler)
        sax_parser.parse(filename)
    except (SAXParseException, Exception):
        pass

    xml_models = list(handler.xml_model_attributes)
    root_attrs = dict(handler.root_attributes)

    # Supplement with lxml's parsed tree in case SAX stopped early or missed attributes
    try:
        root = doc.getroot()
        if root is not None:
            pis: list[dict[str, str]] = []
            node = root.getprevious()
            while node is not None:
                if (
                    isinstance(node, lxml.etree._ProcessingInstruction)
                    and node.target == "xml-model"
                ):
                    attrib = dict(node.attrib)
                    if attrib:
                        pis.append(attrib)
                node = node.getprevious()
            pis.reverse()
            for pi in pis:
                if pi not in xml_models:
                    xml_models.append(pi)

            xsi_no_ns = root.attrib.get(
                "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
            ) or root.attrib.get("xsi:noNamespaceSchemaLocation")
            if xsi_no_ns and "xsi:noNamespaceSchemaLocation" not in root_attrs:
                root_attrs["xsi:noNamespaceSchemaLocation"] = xsi_no_ns
    except Exception:
        pass

    return xml_models, root_attrs


def _get_validator(kind: str, schema_path: str) -> Any:
    """Compile and cache an lxml validator (xsd, rng, or sch)."""
    cache_key = (kind, schema_path)
    if cache_key in _VALIDATOR_CACHE:
        return _VALIDATOR_CACHE[cache_key]

    schema_parser = lxml.etree.XMLParser(no_network=True)
    schema_doc = lxml.etree.parse(schema_path, parser=schema_parser)
    if kind == "xsd":
        validator = lxml.etree.XMLSchema(schema_doc)
    elif kind == "rng":
        validator = lxml.etree.RelaxNG(schema_doc)
    elif kind == "sch":
        if _isoschematron is not None:
            try:
                validator = _isoschematron.Schematron(schema_doc)
            except Exception:
                validator = lxml.etree.Schematron(schema_doc)
        else:
            validator = lxml.etree.Schematron(schema_doc)
    else:
        raise ValueError(f"Unsupported schema type: {kind}")

    _VALIDATOR_CACHE[cache_key] = validator
    return validator


def validate_xml_file(
    filename: str,
    temp_dir: str,
    extra_schemas: list[str] | None = None,
    extra_relaxng: list[str] | None = None,
    extra_schematron: list[str] | None = None,
) -> str | None:
    """Validate a single XML file for well-formedness and against its declared schemas.

    Returns None if valid, or a multi-line error string if invalid.
    """
    xml_parser = lxml.etree.XMLParser(no_network=True)
    try:
        doc = lxml.etree.parse(filename, parser=xml_parser)
    except (lxml.etree.XMLSyntaxError, OSError) as e:
        return f"{filename}: {e}\n{filename} fails to parse"

    xml_file_dir = os.path.dirname(os.path.abspath(filename))
    xml_models, root_attrs = _extract_validation_specs(filename, doc)

    validations: list[tuple[str, str]] = []
    for attributes in xml_models:
        schematypens = attributes.get("schematypens")
        href = attributes.get("href")
        if schematypens is None or href is None:
            continue
        if schematypens == "http://www.w3.org/2001/XMLSchema":
            validations.append(("xsd", get_local_schema_path(href, temp_dir, xml_file_dir)))
        elif schematypens == "http://relaxng.org/ns/structure/1.0":
            validations.append(("rng", get_local_schema_path(href, temp_dir, xml_file_dir)))
        elif schematypens == "http://purl.oclc.org/dsdl/schematron":
            validations.append(("sch", get_local_schema_path(href, temp_dir, xml_file_dir)))

    if "xsi:noNamespaceSchemaLocation" in root_attrs:
        schema_path = get_local_schema_path(
            root_attrs["xsi:noNamespaceSchemaLocation"], temp_dir, xml_file_dir
        )
        validations.append(("xsd", schema_path))

    for s in extra_schemas or []:
        validations.append(("xsd", get_local_schema_path(s, temp_dir, xml_file_dir)))
    for r in extra_relaxng or []:
        validations.append(("rng", get_local_schema_path(r, temp_dir, xml_file_dir)))
    for sch in extra_schematron or []:
        validations.append(("sch", get_local_schema_path(sch, temp_dir, xml_file_dir)))

    error_messages: list[str] = []
    for kind, schema_path in validations:
        try:
            validator = _get_validator(kind, schema_path)
        except Exception as e:
            error_messages.append(
                f"Failed to load {kind.upper()} schema '{schema_path}' for '{filename}': {e}"
            )
            continue

        if not validator.validate(doc):
            for entry in validator.error_log:
                error_messages.append(str(entry))
            error_messages.append(f"{filename} fails to validate")

    if error_messages:
        return "\n".join(error_messages)
    return None


def _is_excluded(path: str, name: str, excludes: list[str]) -> bool:
    """Return True if a file or directory matches any exclusion pattern."""
    if not excludes:
        return False
    norm_path = os.path.normpath(path)
    for pattern in excludes:
        if name == pattern or norm_path == os.path.normpath(pattern):
            return True
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(norm_path, pattern):
            return True
    return False


def get_files(paths: list[str], extensions: list[str], excludes: list[str] | None = None) -> list[str]:
    """Discover XML files from the given file or directory paths."""
    if excludes is None:
        excludes = []
    normalized_exts = {"." + e.lstrip(".") for e in extensions}
    files: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                if "AMENT_IGNORE" in dirnames + filenames or "COLCON_IGNORE" in dirnames + filenames:
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames if d[0] not in [".", "_"]]
                dirnames[:] = [
                    d for d in dirnames if not _is_excluded(os.path.join(dirpath, d), d, excludes)
                ]
                dirnames.sort()

                for filename in sorted(filenames):
                    full_path = os.path.join(dirpath, filename)
                    if _is_excluded(full_path, filename, excludes):
                        continue
                    _, ext = os.path.splitext(filename)
                    if ext not in normalized_exts:
                        continue
                    files.append(full_path)
        elif os.path.isfile(path):
            if not _is_excluded(path, os.path.basename(path), excludes):
                files.append(path)
    return [os.path.normpath(f) for f in files]


def get_xunit_content(
    report: list[tuple[str, str | None]],
    testname: str,
    elapsed: float,
) -> str:
    """Format validation results as an XUnit/JUnit XML document."""
    test_count = len(report)
    error_count = len([r for r in report if r[1]])
    data = {
        "testname": testname,
        "test_count": test_count,
        "error_count": error_count,
        "time": "%.3f" % round(elapsed, 3),
    }
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite
  name="%(testname)s"
  tests="%(test_count)d"
  errors="0"
  failures="%(error_count)d"
  time="%(time)s"
>
""" % data

    for filename, diff_lines in report:
        if diff_lines:
            data = {
                "quoted_location": quoteattr(filename),
                "testname": testname,
                "quoted_message": quoteattr("Diff with %d lines" % len(diff_lines)),
                "cdata": "".join(diff_lines),
            }
            xml += """  <testcase
    name=%(quoted_location)s
    classname="%(testname)s"
  >
      <failure message=%(quoted_message)s><![CDATA[%(cdata)s]]></failure>
  </testcase>
""" % data
        else:
            data = {
                "quoted_location": quoteattr(filename),
                "testname": testname,
            }
            xml += """  <testcase
    name=%(quoted_location)s
    classname="%(testname)s"/>
""" % data

    data = {
        "escaped_files": escape("".join(["\n* %s" % r[0] for r in report])),
    }
    xml += """  <system-out>Checked files:%(escaped_files)s</system-out>
""" % data

    xml += "</testsuite>\n"
    return xml


def _write_xunit_file(xunit_file: str, report: list[tuple[str, str | None]], elapsed: float) -> None:
    """Write the XUnit report file to disk."""
    abs_xunit = os.path.abspath(xunit_file)
    folder_name = os.path.basename(os.path.dirname(abs_xunit)) or "xmllint"
    file_name = os.path.basename(abs_xunit)
    suffix = ".xml"
    if file_name.endswith(suffix):
        file_name = file_name[: -len(suffix)]
        suffix = ".xunit"
        if file_name.endswith(suffix):
            file_name = file_name[: -len(suffix)]
    testname = "%s.%s" % (folder_name, file_name)

    xml = get_xunit_content(report, testname, elapsed)
    path = os.path.dirname(abs_xunit)
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    with open(abs_xunit, "w", encoding="utf-8") as f:
        f.write(xml)


def xmllint_cli(argv: list[str] | None = None) -> int:
    """Drop-in xmllint CLI wrapper supporting --noout, --schema, --relaxng, --schematron."""
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(prog="xmllint", add_help=False)
    parser.add_argument("--noout", action="store_true")
    parser.add_argument("--schema", action="append", default=[])
    parser.add_argument("--relaxng", action="append", default=[])
    parser.add_argument("--schematron", action="append", default=[])
    parser.add_argument("--version", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("files", nargs="*")
    args, _ = parser.parse_known_args(argv)

    if args.version:
        print("xmllint: using libxml version (lxml.etree bundled)")
        return 0
    if args.help or not args.files:
        print("Usage: xmllint [--noout] [--schema SCHEMA] [--relaxng RNG] [--schematron SCH] FILE...")
        return 0 if args.help else 1

    rc = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        for filename in args.files:
            errors = validate_xml_file(
                filename,
                temp_dir,
                extra_schemas=args.schema,
                extra_relaxng=args.relaxng,
                extra_schematron=args.schematron,
            )
            if errors is not None:
                print(errors, file=sys.stderr)
                rc = 1
            elif not args.noout:
                with open(filename, "r", encoding="utf-8", errors="replace") as f:
                    sys.stdout.write(f.read())
    return rc


def main(argv: list[str] | None = None) -> Literal[0, 1]:
    """Entry point for ros-code-standard-xmllint."""
    if argv is None:
        argv = sys.argv[1:]

    default_extensions = ["xml"]

    parser = argparse.ArgumentParser(
        description="Check XML markup using lxml.etree and bundled ROS XSD schemas.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[os.curdir],
        help="The files or directories to check. For directories, only files ending "
        "in %s will be considered (unless overruled by the --extensions "
        "option)" % ", ".join(["'.%s'" % e for e in default_extensions]),
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="Exclude specific file names and directory names from the check",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=default_extensions,
        help="The file extensions of the files to check",
    )
    parser.add_argument(
        "--xunit-file",
        help="Generate a xunit compliant XML file",
    )
    parser.add_argument(
        "--noout",
        action="store_true",
        help="Compatibility flag for raw xmllint invocation",
    )
    parser.add_argument(
        "--schema",
        action="append",
        default=[],
        help="Additional XSD schema(s) to validate against",
    )
    parser.add_argument(
        "--relaxng",
        action="append",
        default=[],
        help="Additional RelaxNG schema(s) to validate against",
    )
    parser.add_argument(
        "--schematron",
        action="append",
        default=[],
        help="Additional Schematron schema(s) to validate against",
    )
    args = parser.parse_args(argv)

    if args.noout:
        return 0 if xmllint_cli(argv) == 0 else 1

    start_time = time.time()

    xunit_file = args.xunit_file
    if not xunit_file and os.environ.get("MANYLINT_JUNIT_DIR"):
        xunit_file = os.path.join(os.environ["MANYLINT_JUNIT_DIR"], "xmllint.xunit.xml")

    files = get_files(args.paths, args.extensions, args.exclude)
    if not files:
        print("No files found", file=sys.stderr)
        if xunit_file:
            _write_xunit_file(xunit_file, [], time.time() - start_time)
        return 1
    files = [os.path.abspath(f) for f in files]

    report: list[tuple[str, str | None]] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for filename in files:
            errors = validate_xml_file(
                filename,
                temp_dir,
                extra_schemas=args.schema,
                extra_relaxng=args.relaxng,
                extra_schematron=args.schematron,
            )
            rel_filename = os.path.relpath(filename, start=os.getcwd())
            report.append((rel_filename, errors))

    for filename, errors in report:
        if errors is not None:
            print("File '%s' is invalid:" % filename, file=sys.stderr)
            for line in errors.splitlines():
                print(line, file=sys.stderr)
            print("", file=sys.stderr)
        else:
            print("File '%s' is valid" % filename)
            print("")

    error_count = sum(1 if r[1] else 0 for r in report)
    if not error_count:
        print("No problems found")
        rc: Literal[0, 1] = 0
    else:
        print("%d files are invalid" % error_count, file=sys.stderr)
        rc = 1

    if xunit_file:
        _write_xunit_file(xunit_file, report, time.time() - start_time)

    return rc


if __name__ == "__main__":
    sys.exit(main())
