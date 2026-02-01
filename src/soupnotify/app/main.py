import logging

from fastapi import FastAPI

from soupnotify.core.config import load_settings
from soupnotify.core.storage import Storage


settings = load_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI()
storage = Storage(settings.database_url)


@app.get("/healthz")
async def healthz() -> dict:
    db_ok = storage.ping()
    last_poll_at = storage.get_poll_state("last_poll_at")
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "last_poll_at": last_poll_at,
    }
