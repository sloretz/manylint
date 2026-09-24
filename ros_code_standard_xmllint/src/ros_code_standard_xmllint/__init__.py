"""Self-contained ROS 2 XML linter and schema validator."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

from ros_code_standard_xmllint.cli import get_schemas_dir
from ros_code_standard_xmllint.cli import main

__all__ = [
    "get_executable",
    "get_schemas_dir",
    "main",
    "run",
]


def get_executable() -> str:
    """Return the path to the xmllint / ros-code-standard-xmllint executable."""
    exe = shutil.which("ros-code-standard-xmllint")
    if exe:
        return exe
    bundled = Path(__file__).resolve().parent / "bin" / "xmllint"
    if bundled.is_file():
        return str(bundled)
    exe = shutil.which("xmllint")
    if exe:
        return exe
    return sys.executable


def run(argv: list[str] | None = None) -> int:
    """Run the XML linter with the provided command-line arguments."""
    return main(argv if argv is not None else sys.argv[1:])
