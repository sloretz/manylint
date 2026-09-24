"""ROS 2 flake8 code standard linter package."""

from __future__ import annotations

import sys

from ros_code_standard_flake8.cli import main

__version__ = "0.1.0"


def get_executable() -> None:
    """Return None as flake8 is a pure-Python linter."""
    return None


def run(argv: list[str] | None = None) -> int:
    """Run the flake8 CLI."""
    if argv is None:
        argv = sys.argv[1:]
    return main(argv=argv)


__all__ = ["__version__", "get_executable", "main", "run"]
