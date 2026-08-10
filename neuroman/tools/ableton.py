# neuroman/tools/ableton.py
"""Producer Pal REST adapter with retries and circuit breaker."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..resilience import ErrorKind, NeuroError, get_breaker, retry_async

log = logging.getLogger("neuroman.tools.ableton")


class AbletonController:
    """Wrapper okolo Producer Pal REST API (Ableton Live, default :3350)."""

    def __init__(self, base_url: str = "http://localhost:3350") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
        self._configured = False
        self._breaker = get_breaker("ableton")

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _ensure_config(self) -> None:
        if self._configured:
            return

        async def _setup() -> None:
            try:
                await self.client.post(
                    f"{self.base_url}/api/tools/ppal-connect?format=json",
                    json={},
                    timeout=10.0,
                )
                await self.client.post(
                    f"{self.base_url}/config",
                    json={"notation": "midi-json"},
                    timeout=2.0,
                )
            except httpx.HTTPError as exc:
                log.warning("ableton config soft-fail: %s", exc)

        await _setup()
        self._configured = True

    async def read_live_set(self) -> dict[str, Any]:
        return await self.call_tool("ppal-read-live-set", {})

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_config()
        url = f"{self.base_url}/api/tools/{tool_name}?format=json"

        async def _once() -> dict[str, Any]:
            try:
                response = await self.client.post(url, json=args)
            except httpx.TimeoutException as exc:
                raise NeuroError(
                    message="Producer Pal timeout.",
                    kind=ErrorKind.TIMEOUT,
                    source="ableton",
                    detail=str(exc),
                ) from exc
            except httpx.RequestError as exc:
                raise NeuroError(
                    message=(
                        f"Nelze se spojit s Producer Pal na {self.base_url}. "
                        "Over, ze Ableton Live bezi a device je aktivni."
                    ),
                    kind=ErrorKind.NETWORK,
                    source="ableton",
                    detail=str(exc),
                ) from exc

            if response.status_code == 404:
                raise NeuroError(
                    message=f"Nastroj '{tool_name}' nenalezen nebo deaktivovan.",
                    kind=ErrorKind.USER,
                    source="ableton",
                    recoverable=False,
                )
            if response.status_code >= 500:
                raise NeuroError(
                    message=f"Producer Pal HTTP {response.status_code}.",
                    kind=ErrorKind.DEPENDENCY_DOWN,
                    source="ableton",
                    detail=response.text[:500],
                )
            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}: {response.text[:300]}"}

            try:
                data = response.json()
            except ValueError as exc:
                raise NeuroError(
                    message="Producer Pal vratil neplatny JSON.",
                    kind=ErrorKind.MALFORMED,
                    source="ableton",
                    detail=response.text[:300],
                ) from exc

            if data.get("isError", False):
                return {"error": data.get("result", "Neznama LOM vyjimka z Producer Pal")}

            result = data.get("result", {})
            warnings = data.get("warnings") or []
            if warnings:
                log.info("ableton warnings: %s", warnings)
                if isinstance(result, dict):
                    result = {**result, "_warnings": warnings}
            return result if isinstance(result, dict) else {"result": result}

        try:
            return await retry_async(
                _once,
                attempts=3,
                base_delay=0.4,
                breaker=self._breaker,
                label=f"ableton:{tool_name}",
            )
        except NeuroError as exc:
            log.error("ableton call_tool failed: %s | %s", exc, exc.detail)
            return {"error": exc.user_line(), "kind": exc.kind.value, "detail": exc.detail}
