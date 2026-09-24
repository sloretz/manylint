import sys
from typing import Optional, Sequence

from ros_code_standard_lint_cmake.cli import main


def run(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return main(list(argv))


def get_executable() -> None:
    return None


__all__ = ["run", "get_executable", "main"]
