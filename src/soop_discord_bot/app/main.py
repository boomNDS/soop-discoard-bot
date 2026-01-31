import logging

from fastapi import FastAPI
from dotenv import load_dotenv

from soop_discord_bot.core.config import load_settings


app = FastAPI(title="SOOP Discord Bot API")


def _configure_logging() -> None:
    load_dotenv()
    settings = load_settings()
    logging.basicConfig(level=settings.log_level.upper())


@app.on_event("startup")
async def startup() -> None:
    _configure_logging()


@app.get("/")
async def root() -> dict:
    return {"status": "ok"}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "healthy"}


@app.get("/readyz")
async def readyz() -> dict:
    return {"status": "ready"}
