from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import Database
from app.schemas import FilesystemRunRequest, ScheduleRequest, TLSRunRequest
from app.services.runs import RunService, isoformat


class ScheduleService:
    def __init__(self, database: Database, runs: RunService) -> None:
        self.database = database
        self.runs = runs
        self.scheduler = AsyncIOScheduler(timezone=UTC)

    async def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
        for schedule in await self.list():
            if schedule["enabled"]:
                await self._register(schedule)

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def list(self) -> list[dict[str, Any]]:
        rows = await self.database.fetch_all("SELECT * FROM schedules ORDER BY created_at DESC")
        return [deserialize_schedule(row) for row in rows]

    async def create(self, request: ScheduleRequest) -> dict[str, Any]:
        schedule_id = uuid4().hex
        now = isoformat(datetime.now(UTC))
        config = schedule_config(request)
        await self.database.execute(
            """
            INSERT INTO schedules (
                id, name, scan_type, interval_minutes, enabled, config_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                request.name,
                request.scan_type,
                request.interval_minutes,
                int(request.enabled),
                json.dumps(config),
                now,
                now,
            ),
        )
        schedule = await self.get(schedule_id)
        if schedule["enabled"]:
            await self._register(schedule)
        return await self.get(schedule_id)

    async def set_enabled(self, schedule_id: str, enabled: bool) -> dict[str, Any]:
        await self.get(schedule_id)
        await self.database.execute(
            "UPDATE schedules SET enabled = ?, updated_at = ? WHERE id = ?",
            (int(enabled), isoformat(datetime.now(UTC)), schedule_id),
        )
        job = self.scheduler.get_job(schedule_id)
        if job:
            self.scheduler.remove_job(schedule_id)
        schedule = await self.get(schedule_id)
        if enabled:
            await self._register(schedule)
        return await self.get(schedule_id)

    async def delete(self, schedule_id: str) -> None:
        await self.get(schedule_id)
        job = self.scheduler.get_job(schedule_id)
        if job:
            self.scheduler.remove_job(schedule_id)
        await self.database.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))

    async def get(self, schedule_id: str) -> dict[str, Any]:
        row = await self.database.fetch_one("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        if not row:
            raise LookupError(schedule_id)
        return deserialize_schedule(row)

    async def _register(self, schedule: dict[str, Any]) -> None:
        trigger = IntervalTrigger(minutes=schedule["interval_minutes"], timezone=UTC)
        self.scheduler.add_job(
            self._execute,
            trigger=trigger,
            args=[schedule["id"]],
            id=schedule["id"],
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        job = self.scheduler.get_job(schedule["id"])
        if job and job.next_run_time:
            await self.database.execute(
                "UPDATE schedules SET next_run_at = ? WHERE id = ?",
                (isoformat(job.next_run_time), schedule["id"]),
            )

    async def _execute(self, schedule_id: str) -> None:
        schedule = await self.get(schedule_id)
        if not schedule["enabled"]:
            return
        config = schedule["config"]
        if schedule["scan_type"] == "filesystem":
            await self.runs.start_filesystem(FilesystemRunRequest(**config), trigger="scheduled")
        else:
            await self.runs.start_tls(TLSRunRequest(**config), trigger="scheduled")
        job = self.scheduler.get_job(schedule_id)
        await self.database.execute(
            "UPDATE schedules SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (
                isoformat(datetime.now(UTC)),
                isoformat(job.next_run_time) if job and job.next_run_time else None,
                schedule_id,
            ),
        )


def schedule_config(request: ScheduleRequest) -> dict[str, Any]:
    if request.scan_type == "filesystem":
        return (request.filesystem or FilesystemRunRequest()).model_dump()
    return (request.tls or TLSRunRequest()).model_dump()


def deserialize_schedule(row: dict[str, Any]) -> dict[str, Any]:
    row["enabled"] = bool(row["enabled"])
    row["config"] = json.loads(row.pop("config_json", "{}"))
    return row
