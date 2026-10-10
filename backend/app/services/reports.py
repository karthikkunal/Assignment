from __future__ import annotations

import json
from typing import Any

from app.database import Database
from app.services.runs import RunNotFoundError, RunService


class ReportService:
    def __init__(self, database: Database, runs: RunService) -> None:
        self.database = database
        self.runs = runs

    async def filesystem(self, run_id: str) -> dict[str, Any]:
        run = await self.runs.get_run(run_id)
        if run["scan_type"] != "filesystem":
            raise RunNotFoundError(run_id)
        observations = await self.database.fetch_all(
            "SELECT * FROM filesystem_observations WHERE run_id = ? ORDER BY path, chain_position",
            (run_id,),
        )
        for observation in observations:
            observation["san_entries"] = json.loads(observation.pop("san_json", "[]"))
            observation["duplicate"] = bool(observation["duplicate"])
        summary = await self.database.fetch_one(
            """
            SELECT
                COUNT(*) AS certificates_found,
                COUNT(DISTINCT NULLIF(fingerprint_sha256, '')) AS unique_certificates,
                SUM(CASE WHEN validity_status = 'valid' THEN 1 ELSE 0 END) AS valid,
                SUM(CASE WHEN validity_status = 'expiring' THEN 1 ELSE 0 END) AS expiring,
                SUM(CASE WHEN validity_status = 'expired' THEN 1 ELSE 0 END) AS expired,
                SUM(CASE WHEN parsing_status != 'parsed' THEN 1 ELSE 0 END) AS parse_failed,
                SUM(CASE WHEN duplicate = 1 THEN 1 ELSE 0 END) AS duplicate_observations
            FROM filesystem_observations WHERE run_id = ?
            """,
            (run_id,),
        )
        return {
            "run": run,
            "summary": summary or {},
            "distributions": {
                "validity": await self._distribution("filesystem_observations", "validity_status", run_id),
                "algorithms": await self._distribution(
                    "filesystem_observations", "public_key_algorithm", run_id
                ),
                "key_sizes": await self._distribution(
                    "filesystem_observations", "CAST(public_key_size AS TEXT)", run_id
                ),
                "issuers": await self._distribution("filesystem_observations", "issuer", run_id, limit=8),
                "locations": await self._distribution(
                    "filesystem_observations", "scan_root", run_id, limit=8
                ),
            },
            "observations": observations,
            "graph": await self.graph(run_id),
        }

    async def tls(self, run_id: str) -> dict[str, Any]:
        run = await self.runs.get_run(run_id)
        if run["scan_type"] != "tls":
            raise RunNotFoundError(run_id)
        observations = await self.database.fetch_all(
            "SELECT * FROM tls_observations WHERE run_id = ? ORDER BY observed_at DESC",
            (run_id,),
        )
        summary = await self.database.fetch_one(
            """
            SELECT
                COALESCE(SUM(event_count), 0) AS events_observed,
                COUNT(DISTINCT destination_ip || ':' || destination_port) AS unique_endpoints,
                COUNT(DISTINCT destination_port) AS unique_ports,
                COUNT(DISTINCT NULLIF(peer_certificate_fingerprint, '')) AS certificates_observed,
                SUM(CASE WHEN handshake_outcome = 'succeeded' THEN 1 ELSE 0 END) AS successful_handshakes,
                SUM(CASE WHEN error != '' THEN 1 ELSE 0 END) AS errors
            FROM tls_observations WHERE run_id = ?
            """,
            (run_id,),
        )
        relationship_count = await self.database.fetch_one(
            "SELECT COUNT(*) AS count FROM relationship_edges WHERE run_id = ?", (run_id,)
        )
        if summary is not None:
            summary["mapped_relationships"] = (relationship_count or {}).get("count", 0)
        activity = await self.database.fetch_all(
            """
            SELECT substr(observed_at, 1, 16) AS label, SUM(event_count) AS value
            FROM tls_observations WHERE run_id = ?
            GROUP BY substr(observed_at, 1, 16) ORDER BY label
            """,
            (run_id,),
        )
        return {
            "run": run,
            "summary": summary or {},
            "distributions": {
                "tls_versions": await self._distribution("tls_observations", "tls_version", run_id),
                "cipher_suites": await self._distribution(
                    "tls_observations", "cipher_suite", run_id, limit=8, weighted=True
                ),
                "endpoints": await self._distribution(
                    "tls_observations",
                    "COALESCE(NULLIF(hostname, ''), destination_ip) || ':' || destination_port",
                    run_id,
                    limit=8,
                    weighted=True,
                ),
                "certificate_posture": await self._distribution(
                    "tls_observations", "certificate_status", run_id
                ),
                "activity": activity,
            },
            "observations": observations,
            "graph": await self.graph(run_id),
        }

    async def graph(self, run_id: str) -> dict[str, list[dict[str, Any]]]:
        nodes = await self.database.fetch_all(
            """
            SELECT node_key AS id, node_type AS type, label, metadata_json
            FROM relationship_nodes WHERE run_id = ?
            """,
            (run_id,),
        )
        for node in nodes:
            node["metadata"] = json.loads(node.pop("metadata_json", "{}"))
        edges = await self.database.fetch_all(
            """
            SELECT source_key AS source, target_key AS target, edge_type AS type,
                   weight, first_seen, last_seen, evidence_json
            FROM relationship_edges WHERE run_id = ? ORDER BY weight DESC
            """,
            (run_id,),
        )
        for edge in edges:
            edge["evidence"] = json.loads(edge.pop("evidence_json", "{}"))
        return {"nodes": nodes, "edges": edges}

    async def _distribution(
        self,
        table: str,
        expression: str,
        run_id: str,
        limit: int = 12,
        weighted: bool = False,
    ) -> list[dict[str, Any]]:
        value = "SUM(event_count)" if weighted else "COUNT(*)"
        return await self.database.fetch_all(
            f"""
            SELECT {expression} AS label, {value} AS value
            FROM {table}
            WHERE run_id = ? AND COALESCE({expression}, '') != ''
            GROUP BY {expression} ORDER BY value DESC LIMIT ?
            """,
            (run_id, limit),
        )
