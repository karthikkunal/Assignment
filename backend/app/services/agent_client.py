from __future__ import annotations

from typing import Any

import httpx


class AgentClientError(RuntimeError):
    pass


class AgentClient:
    def __init__(self, base_url: str, token: str = "") -> None:
        headers = {"X-Agent-Token": token} if token else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(10.0),
        )

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AgentClientError(str(error)) from error

    async def start_filesystem_scan(self, run_id: str, roots: list[str]) -> None:
        await self._post("/v1/scans/filesystem", {"run_id": run_id, "roots": roots})

    async def start_tls_scan(self, run_id: str, duration_seconds: int, probe_targets: list[str]) -> None:
        await self._post(
            "/v1/scans/tls",
            {
                "run_id": run_id,
                "duration_seconds": duration_seconds,
                "probe_targets": probe_targets,
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> None:
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise AgentClientError(str(error)) from error
