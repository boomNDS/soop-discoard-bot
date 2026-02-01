import asyncio
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
        self._client = httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_live_user_ids(self, target_ids: Iterable[str]) -> set[str]:
        targets = {str(value) for value in target_ids if value}
        if not targets:
            return set()

        results = await asyncio.gather(
            *[self.fetch_broad_info(streamer_id) for streamer_id in targets],
            return_exceptions=True,
        )
        found: set[str] = set()
        for streamer_id, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.warning("SOOP channel fetch failed for %s: %s", streamer_id, result)
                continue
            if result:
                found.add(streamer_id)
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
        if not response.content:
            logger.warning("SOOP channel response empty for %s", streamer_id)
            return None
        try:
            payload: dict[str, Any] = response.json()
        except ValueError:
            snippet = response.text[:200]
            logger.warning("SOOP channel response not JSON for %s: %s", streamer_id, snippet)
            return None
        return payload if payload else None

    def build_thumbnail_url(self, broad_no: str | int | None) -> str | None:
        if not broad_no:
            if "{broad_no}" in self._thumbnail_url_template:
                return None
            return self._thumbnail_url_template
        try:
            return self._thumbnail_url_template.format(broad_no=broad_no)
        except Exception:
            return None

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
                response = await self._client.get(url, params=params, headers=headers)
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
