"""ROS 2 cpplint code standard linter package."""

from __future__ import annotations

import sys

from ros_code_standard_cpplint.cli import main

__version__ = "0.1.0"


def get_executable() -> None:
    """Return None as cpplint is a pure-Python linter."""
    return None


def run(argv: list[str] | None = None) -> int:
    """Run the cpplint CLI."""
    if argv is None:
        argv = sys.argv[1:]
    return main(argv=argv)


__all__ = ["__version__", "get_executable", "main", "run"]
