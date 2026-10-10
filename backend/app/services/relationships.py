from __future__ import annotations

import hashlib
import json
import socket
from collections.abc import Iterable
from typing import Any

from app.schemas import CertificateObservationIn, TLSObservationIn


def filesystem_relationships(
    observations: Iterable[CertificateObservationIn],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graph = RelationshipGraph()
    host_key = "host:local"
    graph.node(host_key, "host", socket.gethostname(), {"scope": "local"})

    for observation in observations:
        certificate_identity = observation.fingerprint_sha256 or stable_identity(
            observation.subject, observation.serial_number, observation.path
        )
        certificate_key = f"certificate:{certificate_identity}"
        graph.node(
            certificate_key,
            "certificate",
            observation.subject or observation.filename,
            {
                "fingerprint": observation.fingerprint_sha256,
                "issuer": observation.issuer,
                "status": observation.validity_status,
            },
        )
        graph.edge(
            host_key,
            certificate_key,
            "stores",
            observation.discovered_at.isoformat(),
            1,
            {"path": observation.path, "confidence": observation.evidence_confidence},
        )
        if observation.owner_process and observation.owner_process != "unavailable":
            process_key = f"process:{stable_identity(observation.owner_process)}"
            graph.node(process_key, "process", observation.owner_process, {})
            graph.edge(
                process_key,
                certificate_key,
                "owns",
                observation.discovered_at.isoformat(),
                1,
                {"path": observation.path},
            )
    return graph.export()


def tls_relationships(
    observations: Iterable[TLSObservationIn],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graph = RelationshipGraph()
    host_key = "host:local"
    graph.node(host_key, "host", socket.gethostname(), {"scope": "local"})

    for observation in observations:
        source_key = host_key
        if observation.pid or observation.process_name:
            process_identity = f"{observation.pid}:{observation.process_name or observation.executable}"
            source_key = f"process:{stable_identity(process_identity)}"
            graph.node(
                source_key,
                "process",
                observation.process_name or f"PID {observation.pid}",
                {"pid": observation.pid, "executable": observation.executable},
            )
            graph.edge(
                host_key,
                source_key,
                "runs",
                observation.observed_at.isoformat(),
                1,
                {},
            )

        endpoint_host = observation.hostname or observation.destination_ip or "unknown"
        endpoint_key = f"endpoint:{endpoint_host.casefold()}:{observation.destination_port}"
        graph.node(
            endpoint_key,
            "endpoint",
            f"{endpoint_host}:{observation.destination_port}",
            {
                "ip": observation.destination_ip,
                "port": observation.destination_port,
                "direction": observation.direction,
            },
        )
        event_count = max(observation.event_count, 1)
        graph.edge(
            source_key,
            endpoint_key,
            "communicates_with",
            observation.observed_at.isoformat(),
            event_count,
            {
                "transport": observation.transport,
                "tls_version": observation.tls_version,
                "capture_method": observation.capture_method,
            },
        )

        if observation.local_service:
            service_identity = stable_identity(observation.local_service, str(observation.destination_port))
            service_key = f"service:{service_identity}"
            graph.node(
                service_key,
                "service",
                observation.local_service,
                {"port": observation.destination_port},
            )
            graph.edge(
                endpoint_key,
                service_key,
                "provides",
                observation.observed_at.isoformat(),
                event_count,
                {},
            )

        if observation.peer_certificate_fingerprint:
            certificate_key = f"certificate:{observation.peer_certificate_fingerprint}"
            graph.node(
                certificate_key,
                "certificate",
                observation.peer_certificate_subject or observation.peer_certificate_fingerprint[:16],
                {
                    "fingerprint": observation.peer_certificate_fingerprint,
                    "issuer": observation.peer_certificate_issuer,
                    "status": observation.certificate_status,
                },
            )
            graph.edge(
                endpoint_key,
                certificate_key,
                "presents",
                observation.observed_at.isoformat(),
                event_count,
                {"sni": observation.sni},
            )
            graph.edge(
                source_key,
                certificate_key,
                "observes",
                observation.observed_at.isoformat(),
                event_count,
                {"confidence": observation.evidence_confidence},
            )
    return graph.export()


class RelationshipGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    def node(self, key: str, node_type: str, label: str, metadata: dict[str, Any]) -> None:
        self.nodes[key] = {
            "node_key": key,
            "node_type": node_type,
            "label": label,
            "metadata_json": json.dumps(metadata, separators=(",", ":")),
        }

    def edge(
        self,
        source_key: str,
        target_key: str,
        edge_type: str,
        observed_at: str,
        weight: int,
        evidence: dict[str, Any],
    ) -> None:
        key = (source_key, target_key, edge_type)
        if key in self.edges:
            edge = self.edges[key]
            edge["weight"] += weight
            edge["last_seen"] = max(edge["last_seen"], observed_at)
            return
        self.edges[key] = {
            "source_key": source_key,
            "target_key": target_key,
            "edge_type": edge_type,
            "weight": weight,
            "first_seen": observed_at,
            "last_seen": observed_at,
            "evidence_json": json.dumps(evidence, separators=(",", ":")),
        }

    def export(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return list(self.nodes.values()), list(self.edges.values())


def stable_identity(*parts: str) -> str:
    value = "\x1f".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()
