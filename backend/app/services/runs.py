from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

import aiosqlite

from app.config import Settings
from app.database import Database
from app.schemas import (
    AgentStatusUpdate,
    FilesystemResultIn,
    FilesystemRunRequest,
    TLSResultIn,
    TLSRunRequest,
)
from app.services.agent_client import AgentClient, AgentClientError
from app.services.relationships import filesystem_relationships, tls_relationships


class RunNotFoundError(LookupError):
    pass


class RunTypeMismatchError(ValueError):
    pass


class RunService:
    def __init__(self, database: Database, agent_client: AgentClient, settings: Settings) -> None:
        self.database = database
        self.agent_client = agent_client
        self.settings = settings

    async def start_filesystem(
        self,
        request: FilesystemRunRequest,
        trigger: Literal["manual", "scheduled"] = "manual",
    ) -> dict[str, Any]:
        roots = request.roots or self.settings.scan_roots
        run = await self._create_run("filesystem", trigger, {"roots": roots})
        try:
            await self.agent_client.start_filesystem_scan(run["id"], roots)
        except AgentClientError as error:
            await self._mark_dispatch_failed(run["id"], str(error))
        return await self.get_run(run["id"])

    async def start_tls(
        self,
        request: TLSRunRequest,
        trigger: Literal["manual", "scheduled"] = "manual",
    ) -> dict[str, Any]:
        targets = request.probe_targets or self.settings.probe_targets
        config = {"duration_seconds": request.duration_seconds, "probe_targets": targets}
        run = await self._create_run("tls", trigger, config)
        try:
            await self.agent_client.start_tls_scan(run["id"], request.duration_seconds, targets)
        except AgentClientError as error:
            await self._mark_dispatch_failed(run["id"], str(error))
        return await self.get_run(run["id"])

    async def update_status(self, run_id: str, update: AgentStatusUpdate) -> dict[str, Any]:
        existing = await self.get_run(run_id)
        if update.status == "running":
            await self.database.execute(
                """
                UPDATE runs
                SET status = ?, started_at = COALESCE(started_at, ?), status_message = ?
                WHERE id = ?
                """,
                (update.status, isoformat(update.timestamp), update.message, run_id),
            )
        elif update.status in {"queued", "failed"}:
            await self.database.execute(
                "UPDATE runs SET status = ?, status_message = ? WHERE id = ?",
                (update.status, update.message, run_id),
            )
        return {**existing, "status": update.status, "status_message": update.message}

    async def ingest_filesystem(self, payload: FilesystemResultIn) -> dict[str, Any]:
        await self._assert_run_type(payload.run_id, "filesystem")
        nodes, edges = filesystem_relationships(payload.observations)
        unique_fingerprints = {
            item.fingerprint_sha256 for item in payload.observations if item.fingerprint_sha256
        }
        async with self.database.connection() as connection:
            await self._clear_run_evidence(connection, payload.run_id)
            await connection.executemany(
                """
                INSERT INTO filesystem_observations (
                    run_id, path, filename, format, discovered_at, scan_root,
                    fingerprint_sha256, serial_number, subject, issuer, san_json,
                    chain_position, public_key_algorithm, public_key_size,
                    signature_algorithm, valid_from, valid_to, days_to_expiry,
                    validity_status, owner_process, parsing_status, access_error,
                    evidence_confidence, duplicate, duplicate_of
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        payload.run_id,
                        item.path,
                        item.filename,
                        item.format,
                        isoformat(item.discovered_at),
                        item.scan_root,
                        item.fingerprint_sha256,
                        item.serial_number,
                        item.subject,
                        item.issuer,
                        json.dumps(item.san_entries),
                        item.chain_position,
                        item.public_key_algorithm,
                        item.public_key_size,
                        item.signature_algorithm,
                        isoformat(item.valid_from),
                        isoformat(item.valid_to),
                        item.days_to_expiry,
                        item.validity_status,
                        item.owner_process,
                        item.parsing_status,
                        item.access_error,
                        item.evidence_confidence,
                        int(item.duplicate),
                        item.duplicate_of,
                    )
                    for item in payload.observations
                ],
            )
            await self._store_graph(connection, payload.run_id, nodes, edges)
            await self._complete_run(
                connection,
                payload.run_id,
                payload.status,
                payload.started_at,
                payload.completed_at,
                len(payload.observations),
                len(unique_fingerprints),
                payload.errors,
                payload.agent_version,
            )
            await connection.commit()
        return await self.get_run(payload.run_id)

    async def ingest_tls(self, payload: TLSResultIn) -> dict[str, Any]:
        await self._assert_run_type(payload.run_id, "tls")
        nodes, edges = tls_relationships(payload.observations)
        endpoints = {
            (item.destination_ip or item.hostname, item.destination_port)
            for item in payload.observations
            if item.destination_ip or item.hostname
        }
        async with self.database.connection() as connection:
            await self._clear_run_evidence(connection, payload.run_id)
            await connection.executemany(
                """
                INSERT INTO tls_observations (
                    run_id, observed_at, source_ip, source_port, destination_ip,
                    destination_port, direction, transport, connection_state,
                    handshake_outcome, hostname, sni, tls_version, cipher_suite,
                    peer_certificate_fingerprint, peer_certificate_subject,
                    peer_certificate_issuer, peer_certificate_valid_to,
                    certificate_status, pid, process_name, executable, local_service,
                    event_count, capture_method, evidence_confidence, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        payload.run_id,
                        isoformat(item.observed_at),
                        item.source_ip,
                        item.source_port,
                        item.destination_ip,
                        item.destination_port,
                        item.direction,
                        item.transport,
                        item.connection_state,
                        item.handshake_outcome,
                        item.hostname,
                        item.sni,
                        item.tls_version,
                        item.cipher_suite,
                        item.peer_certificate_fingerprint,
                        item.peer_certificate_subject,
                        item.peer_certificate_issuer,
                        isoformat(item.peer_certificate_valid_to),
                        item.certificate_status,
                        item.pid,
                        item.process_name,
                        item.executable,
                        item.local_service,
                        item.event_count,
                        item.capture_method,
                        item.evidence_confidence,
                        item.error,
                    )
                    for item in payload.observations
                ],
            )
            await self._store_graph(connection, payload.run_id, nodes, edges)
            await self._complete_run(
                connection,
                payload.run_id,
                payload.status,
                payload.started_at,
                payload.completed_at,
                sum(item.event_count for item in payload.observations),
                len(endpoints),
                payload.errors,
                payload.agent_version,
            )
            await connection.commit()
        return await self.get_run(payload.run_id)

    async def list_runs(
        self,
        scan_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if scan_type:
            conditions.append("scan_type = ?")
            parameters.append(scan_type)
        if status:
            conditions.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        rows = await self.database.fetch_all(
            f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT ?", parameters
        )
        return [deserialize_run(row) for row in rows]

    async def get_run(self, run_id: str) -> dict[str, Any]:
        row = await self.database.fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not row:
            raise RunNotFoundError(run_id)
        return deserialize_run(row)

    async def dashboard(self) -> dict[str, Any]:
        totals = await self.database.fetch_one(
            """
            SELECT
                COUNT(*) AS total_runs,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS active_runs,
                SUM(CASE WHEN scan_type = 'filesystem' THEN 1 ELSE 0 END) AS filesystem_runs,
                SUM(CASE WHEN scan_type = 'tls' THEN 1 ELSE 0 END) AS tls_runs,
                SUM(record_count) AS total_evidence
            FROM runs
            """
        )
        status_counts = await self.database.fetch_all(
            "SELECT status AS label, COUNT(*) AS value FROM runs GROUP BY status ORDER BY value DESC"
        )
        type_counts = await self.database.fetch_all(
            "SELECT scan_type AS label, COUNT(*) AS value FROM runs GROUP BY scan_type ORDER BY value DESC"
        )
        trend = await self.database.fetch_all(
            """
            SELECT substr(created_at, 1, 10) AS date, scan_type, COUNT(*) AS runs,
                   SUM(record_count) AS findings, ROUND(AVG(duration_ms)) AS avg_duration_ms
            FROM runs
            GROUP BY substr(created_at, 1, 10), scan_type
            ORDER BY date ASC
            LIMIT 60
            """
        )
        return {
            "totals": totals or {},
            "status_counts": status_counts,
            "type_counts": type_counts,
            "trend": trend,
            "latest_runs": await self.list_runs(limit=8),
        }

    async def _create_run(self, scan_type: str, trigger: str, config: dict[str, Any]) -> dict[str, Any]:
        run_id = uuid4().hex
        created_at = isoformat(datetime.now(UTC))
        await self.database.execute(
            """
            INSERT INTO runs (id, scan_type, trigger_type, status, created_at, config_json)
            VALUES (?, ?, ?, 'queued', ?, ?)
            """,
            (run_id, scan_type, trigger, created_at, json.dumps(config)),
        )
        return await self.get_run(run_id)

    async def _mark_dispatch_failed(self, run_id: str, message: str) -> None:
        now = isoformat(datetime.now(UTC))
        await self.database.execute(
            """
            UPDATE runs SET status = 'failed', completed_at = ?, duration_ms = 0,
                            error_count = 1, error_summary = ?, status_message = ?
            WHERE id = ?
            """,
            (now, f"Agent unavailable: {message}"[:2000], "Agent command could not be delivered", run_id),
        )

    async def _assert_run_type(self, run_id: str, expected_type: str) -> None:
        run = await self.get_run(run_id)
        if run["scan_type"] != expected_type:
            raise RunTypeMismatchError(f"run {run_id} is {run['scan_type']}, not {expected_type}")

    async def _clear_run_evidence(self, connection: aiosqlite.Connection, run_id: str) -> None:
        await connection.execute("DELETE FROM relationship_edges WHERE run_id = ?", (run_id,))
        await connection.execute("DELETE FROM relationship_nodes WHERE run_id = ?", (run_id,))
        await connection.execute("DELETE FROM filesystem_observations WHERE run_id = ?", (run_id,))
        await connection.execute("DELETE FROM tls_observations WHERE run_id = ?", (run_id,))

    async def _store_graph(
        self,
        connection: aiosqlite.Connection,
        run_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        await connection.executemany(
            """
            INSERT INTO relationship_nodes (run_id, node_key, node_type, label, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (run_id, node["node_key"], node["node_type"], node["label"], node["metadata_json"])
                for node in nodes
            ],
        )
        await connection.executemany(
            """
            INSERT INTO relationship_edges (
                run_id, source_key, target_key, edge_type, weight, first_seen, last_seen, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    edge["source_key"],
                    edge["target_key"],
                    edge["edge_type"],
                    edge["weight"],
                    edge["first_seen"],
                    edge["last_seen"],
                    edge["evidence_json"],
                )
                for edge in edges
            ],
        )

    async def _complete_run(
        self,
        connection: aiosqlite.Connection,
        run_id: str,
        status: str,
        started_at: datetime,
        completed_at: datetime,
        record_count: int,
        unique_count: int,
        errors: list[Any],
        agent_version: str,
    ) -> None:
        duration_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))
        error_summary = "; ".join(
            f"{error.path}: {error.message}" if error.path else error.message for error in errors
        )[:4000]
        await connection.execute(
            """
            UPDATE runs SET status = ?, started_at = ?, completed_at = ?, duration_ms = ?,
                            record_count = ?, unique_count = ?, error_count = ?, error_summary = ?,
                            status_message = ?, agent_version = ?
            WHERE id = ?
            """,
            (
                status,
                isoformat(started_at),
                isoformat(completed_at),
                duration_ms,
                record_count,
                unique_count,
                len(errors),
                error_summary,
                "Evidence received from local agent",
                agent_version,
                run_id,
            ),
        )


def deserialize_run(row: dict[str, Any]) -> dict[str, Any]:
    row["config"] = json.loads(row.pop("config_json", "{}"))
    return row


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
