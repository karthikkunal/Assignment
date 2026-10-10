from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router
from app.config import Settings
from app.database import Database
from app.services.agent_client import AgentClient
from app.services.reports import ReportService
from app.services.runs import RunNotFoundError, RunService, RunTypeMismatchError
from app.services.scheduler import ScheduleService


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]):  # type: ignore[no-untyped-def]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != status.HTTP_404_NOT_FOUND or scope.get("method") != "GET":
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(settings.database_path, settings.migrations_path)
        await database.initialize()
        agent_client = AgentClient(settings.agent_url, settings.agent_token)
        runs = RunService(database, agent_client, settings)
        reports = ReportService(database, runs)
        schedules = ScheduleService(database, runs)

        app.state.settings = settings
        app.state.database = database
        app.state.agent_client = agent_client
        app.state.run_service = runs
        app.state.report_service = reports
        app.state.schedule_service = schedules
        await schedules.start()
        try:
            yield
        finally:
            await schedules.stop()
            await agent_client.close()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Local certificate and TLS metadata discovery API",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Agent-Token"],
    )
    app.include_router(router)

    @app.exception_handler(RunNotFoundError)
    async def run_not_found(_: Request, error: RunNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": f"Run {error} not found"}
        )

    @app.exception_handler(RunTypeMismatchError)
    async def run_type_mismatch(_: Request, error: RunTypeMismatchError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)})

    @app.exception_handler(LookupError)
    async def resource_not_found(_: Request, error: LookupError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Resource {error} not found"},
        )

    if settings.frontend_dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    else:

        @app.get("/", include_in_schema=False)
        async def api_root() -> dict[str, Any]:
            return {"name": settings.app_name, "status": "ready", "docs": "/api/docs"}

    return app


app = create_app()


def run() -> None:
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
