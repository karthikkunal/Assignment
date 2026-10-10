from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest_asyncio

from app.config import Settings
from app.main import create_app


class FakeAgentClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    async def health(self) -> dict[str, Any]:
        return {"status": "healthy", "version": "test", "os": "windows", "active_runs": 0}

    async def start_filesystem_scan(self, run_id: str, roots: list[str]) -> None:
        self.commands.append({"type": "filesystem", "run_id": run_id, "roots": roots})

    async def start_tls_scan(self, run_id: str, duration_seconds: int, probe_targets: list[str]) -> None:
        self.commands.append(
            {
                "type": "tls",
                "run_id": run_id,
                "duration_seconds": duration_seconds,
                "probe_targets": probe_targets,
            }
        )


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, Any, FakeAgentClient]]:
    backend_root = Path(__file__).resolve().parent.parent
    settings = Settings(
        database_path=tmp_path / "test.db",
        migrations_path=backend_root / "migrations",
        frontend_dist=tmp_path / "missing-frontend",
        agent_url="http://127.0.0.1:1",
        default_scan_roots=str(tmp_path),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        fake_agent = FakeAgentClient()
        app.state.run_service.agent_client = fake_agent
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, app, fake_agent
