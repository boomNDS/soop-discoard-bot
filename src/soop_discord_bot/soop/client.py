import json
import logging
from typing import Any, Iterable

import httpx


logger = logging.getLogger(__name__)


class SoopClient:
    def __init__(self, base_url: str, client_id: str, max_pages: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._max_pages = max_pages

    async def fetch_live_user_ids(self, target_ids: Iterable[str]) -> set[str]:
        targets = {str(value) for value in target_ids if value}
        if not targets:
            return set()

        found: set[str] = set()
        page_no = 1
        while page_no <= self._max_pages:
            payload = await self._fetch_broadcast_page(page_no)
            items = _normalize_broadcast_items(payload.get("broad"))
            if not items:
                break

            for item in items:
                user_id = str(item.get("user_id") or "")
                if user_id in targets:
                    found.add(user_id)
            if found == targets:
                break

            total = _parse_int(payload.get("total_cnt"))
            page_block = _parse_int(payload.get("page_block"))
            if total and page_block and page_no * page_block >= total:
                break

            page_no += 1

        return found

    async def _fetch_broadcast_page(self, page_no: int) -> dict[str, Any]:
        url = f"{self._base_url}/broad/list"
        params = {
            "client_id": self._client_id,
            "page_no": str(page_no),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return _parse_soop_payload(response.text)


def _parse_soop_payload(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith(("callback(", "cb(")) and text.endswith(")"):
        text = text[text.find("(") + 1 : -1]
    if text.endswith(";"):
        text = text[:-1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse SOOP payload: %s", raw_text[:200])
        return {}


def _normalize_broadcast_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
