import asyncio
import json
import logging
from typing import Any, Iterable

import httpx


logger = logging.getLogger(__name__)


class SoopClient:
    def __init__(
        self,
        base_url: str,
        client_id: str,
        max_pages: int,
        channel_api_base_url: str,
        hardcode_streamer_id: str | None,
        thumbnail_url_template: str,
        retry_max: int,
        retry_backoff: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._max_pages = max_pages
        self._channel_api_base_url = channel_api_base_url.rstrip("/")
        self._hardcode_streamer_id = hardcode_streamer_id
        self._thumbnail_url_template = thumbnail_url_template
        self._retry_max = max(retry_max, 1)
        self._retry_backoff = max(retry_backoff, 0.1)

    async def fetch_live_user_ids(self, target_ids: Iterable[str]) -> set[str]:
        targets = {str(value) for value in target_ids if value}
        if not targets:
            return set()

        found: set[str] = set()
        if self._hardcode_streamer_id and self._hardcode_streamer_id in targets:
            is_live = await self.fetch_broad_info(self._hardcode_streamer_id) is not None
            if is_live:
                found.add(self._hardcode_streamer_id)
            targets.remove(self._hardcode_streamer_id)
            if not targets:
                return found

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

    async def fetch_broad_info(self, streamer_id: str) -> dict[str, Any] | None:
        url = f"{self._channel_api_base_url}/v1.1/channel/{streamer_id}/home/section/broad"
        headers = {"Accept": "application/json"}
        response = await self._request_with_retry(url, headers=headers, return_response=True)
        if response.status_code == 404:
            logger.warning("SOOP channel not found for %s", streamer_id)
            return None
        if response.status_code == 204:
            return None
        payload: dict[str, Any] = response.json()
        return payload if payload else None

    def build_thumbnail_url(self, broad_no: str | int | None) -> str | None:
        if not broad_no:
            return None
        try:
            return self._thumbnail_url_template.format(broad_no=broad_no)
        except Exception:
            return None

    async def _fetch_broadcast_page(self, page_no: int) -> dict[str, Any]:
        url = f"{self._base_url}/broad/list"
        params = {
            "client_id": self._client_id,
            "page_no": str(page_no),
        }
        response_text = await self._request_with_retry(url, params=params)
        return _parse_soop_payload(response_text)

    async def _request_with_retry(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        return_response: bool = False,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._retry_max):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params, headers=headers)
                if response.status_code >= 500 or response.status_code == 429:
                    raise httpx.HTTPStatusError(
                        f"Retryable status: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    if return_response:
                        return response
                    response.raise_for_status()
                    return response.text
                if return_response:
                    return response
                response.raise_for_status()
                return response.text
            except Exception as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                    status = exc.response.status_code
                    if 400 <= status < 500 and status != 429:
                        raise
                last_error = exc
                await asyncio.sleep(self._retry_backoff * (2**attempt))
        if last_error:
            raise last_error
        raise RuntimeError("SOOP request failed")



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
