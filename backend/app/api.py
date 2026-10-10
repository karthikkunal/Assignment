from __future__ import annotations

import secrets
from typing import Any, Literal

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request, status

from app.schemas import (
    AgentStatusUpdate,
    FilesystemResultIn,
    FilesystemRunRequest,
    ScheduleRequest,
    TLSResultIn,
    TLSRunRequest,
)
from app.services.agent_client import AgentClientError
from app.services.reports import ReportService
from app.services.runs import RunService
from app.services.scheduler import ScheduleService

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    database_ok = await request.app.state.database.fetch_one("SELECT 1 AS ok")
    try:
        agent = await request.app.state.agent_client.health()
        agent_component = {"status": "healthy", **agent}
    except AgentClientError as error:
        agent_component = {"status": "unavailable", "message": str(error)}
    return {
        "status": "healthy" if database_ok else "degraded",
        "components": {
            "api": {"status": "healthy"},
            "database": {"status": "healthy" if database_ok else "unavailable"},
            "agent": agent_component,
        },
    }


@router.get("/config")
async def config(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "default_scan_roots": settings.scan_roots,
        "default_tls_duration_seconds": settings.default_tls_duration_seconds,
        "default_probe_targets": settings.probe_targets,
        "supported_os": "Windows",
        "agent_url": settings.agent_url,
    }


@router.get("/dashboard")
async def dashboard(request: Request) -> dict[str, Any]:
    return await run_service(request).dashboard()


@router.get("/runs")
async def list_runs(
    request: Request,
    scan_type: Literal["filesystem", "tls"] | None = None,
    run_status: Literal["queued", "running", "completed", "partial", "failed"] | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return await run_service(request).list_runs(scan_type, run_status, limit)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    return await run_service(request).get_run(run_id)


@router.post("/runs/filesystem", status_code=status.HTTP_202_ACCEPTED)
async def start_filesystem(payload: FilesystemRunRequest, request: Request) -> dict[str, Any]:
    return await run_service(request).start_filesystem(payload)


@router.post("/runs/tls", status_code=status.HTTP_202_ACCEPTED)
async def start_tls(payload: TLSRunRequest, request: Request) -> dict[str, Any]:
    return await run_service(request).start_tls(payload)


@router.get("/reports/filesystem/{run_id}")
async def filesystem_report(run_id: str, request: Request) -> dict[str, Any]:
    return await report_service(request).filesystem(run_id)


@router.get("/reports/tls/{run_id}")
async def tls_report(run_id: str, request: Request) -> dict[str, Any]:
    return await report_service(request).tls(run_id)


@router.get("/runs/{run_id}/graph")
async def relationship_graph(run_id: str, request: Request) -> dict[str, Any]:
    await run_service(request).get_run(run_id)
    return await report_service(request).graph(run_id)


@router.post("/agent/runs/{run_id}/status")
async def agent_status(
    run_id: str,
    payload: AgentStatusUpdate,
    request: Request,
    x_agent_token: str = Header(default=""),
) -> dict[str, Any]:
    verify_agent_token(request, x_agent_token)
    return await run_service(request).update_status(run_id, payload)


@router.post("/agent/results/filesystem")
async def ingest_filesystem(
    payload: FilesystemResultIn,
    request: Request,
    x_agent_token: str = Header(default=""),
) -> dict[str, Any]:
    verify_agent_token(request, x_agent_token)
    return await run_service(request).ingest_filesystem(payload)


@router.post("/agent/results/tls")
async def ingest_tls(
    payload: TLSResultIn,
    request: Request,
    x_agent_token: str = Header(default=""),
) -> dict[str, Any]:
    verify_agent_token(request, x_agent_token)
    return await run_service(request).ingest_tls(payload)


@router.get("/schedules")
async def list_schedules(request: Request) -> list[dict[str, Any]]:
    return await schedule_service(request).list()


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(payload: ScheduleRequest, request: Request) -> dict[str, Any]:
    return await schedule_service(request).create(payload)


@router.patch("/schedules/{schedule_id}")
async def toggle_schedule(
    schedule_id: str,
    request: Request,
    enabled: bool = Body(embed=True),
) -> dict[str, Any]:
    return await schedule_service(request).set_enabled(schedule_id, enabled)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: str, request: Request) -> None:
    await schedule_service(request).delete(schedule_id)


def verify_agent_token(request: Request, provided_token: str) -> None:
    expected_token = request.app.state.settings.agent_token
    if expected_token and not secrets.compare_digest(expected_token, provided_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")


def run_service(request: Request) -> RunService:
    return request.app.state.run_service


def report_service(request: Request) -> ReportService:
    return request.app.state.report_service


def schedule_service(request: Request) -> ScheduleService:
    return request.app.state.schedule_service
