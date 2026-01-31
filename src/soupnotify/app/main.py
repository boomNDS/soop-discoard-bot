import logging

from fastapi import FastAPI
from dotenv import load_dotenv

from soupnotify.core.config import load_settings
from soupnotify.core.storage import Storage


app = FastAPI(title="SOOP Discord Bot API")


def _configure_logging() -> None:
    load_dotenv()
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="ts=%(asctime)s level=%(levelname)s msg=%(message)s",
    )


@app.on_event("startup")
async def startup() -> None:
    _configure_logging()


@app.get("/")
async def root() -> dict:
    return {"status": "ok"}


@app.get("/healthz")
async def healthz() -> dict:
    settings = load_settings()
    storage = Storage(settings.database_url)
    db_ok = storage.ping()
    return {"status": "healthy", "db": "ok" if db_ok else "error"}


@app.get("/readyz")
async def readyz() -> dict:
    return {"status": "ready"}
