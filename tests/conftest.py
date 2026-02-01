from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config


@contextmanager
def _temp_env(key: str, value: str):
    old = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


def apply_migrations(database_url: str) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with _temp_env("DATABASE_URL", database_url):
        command.upgrade(config, "head")
