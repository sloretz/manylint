from pathlib import Path
import sys


def get_executable() -> Path:
    """Return path to the bundled static cppcheck binary."""
    return Path(__file__).resolve().parent / "bin" / "cppcheck"


def run(argv: list[str] | None = None) -> int:
    """Run the linter with CLI arguments. Return 0 if clean, 1 if violations occurred."""
    from .cli import main

    return main(argv if argv is not None else sys.argv[1:])
