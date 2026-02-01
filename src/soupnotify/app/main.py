import logging

from fastapi import FastAPI

from soupnotify.core.config import load_settings


app = FastAPI()


def _configure_logging() -> None:
    settings = load_settings()
    logging.basicConfig(level=settings.log_level.upper())


@app.on_event("startup")
async def startup() -> None:
    _configure_logging()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
