from .cli import SCHEMA_DIR, main

run = main


def get_executable() -> None:
    return None


def get_schemas_dir():
    return SCHEMA_DIR


__all__ = ['get_executable', 'get_schemas_dir', 'main', 'run']
