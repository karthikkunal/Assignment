from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_filesystem_run_ingestion_report_and_dashboard(api: tuple[Any, Any, Any]) -> None:
    client, _, fake_agent = api
    started = datetime.now(UTC) - timedelta(seconds=2)
    completed = datetime.now(UTC)

    start_response = await client.post("/api/v1/runs/filesystem", json={"roots": [r"C:\certs"]})
    assert start_response.status_code == 202
    run_id = start_response.json()["id"]
    assert fake_agent.commands == [{"type": "filesystem", "run_id": run_id, "roots": [r"C:\certs"]}]

    status_response = await client.post(
        f"/api/v1/agent/runs/{run_id}/status",
        json={"status": "running", "timestamp": started.isoformat(), "message": "Scanning"},
    )
    assert status_response.status_code == 200

    base_observation = {
        "format": "PEM",
        "discovered_at": completed.isoformat(),
        "scan_root": r"C:\certs",
        "fingerprint_sha256": "A" * 64,
        "serial_number": "2A",
        "subject": "CN=service.contoso.com",
        "issuer": "CN=Contoso Test CA",
        "san_entries": ["service.contoso.com"],
        "chain_position": 0,
        "public_key_algorithm": "RSA",
        "public_key_size": 2048,
        "signature_algorithm": "SHA256-RSA",
        "valid_from": (completed - timedelta(days=1)).isoformat(),
        "valid_to": (completed + timedelta(days=90)).isoformat(),
        "days_to_expiry": 90,
        "validity_status": "valid",
        "owner_process": "unavailable",
        "parsing_status": "parsed",
        "access_error": "",
        "evidence_confidence": "high",
        "duplicate_of": "",
    }
    observations = [
        {
            **base_observation,
            "path": r"C:\certs\service.pem",
            "filename": "service.pem",
            "duplicate": False,
        },
        {
            **base_observation,
            "path": r"C:\certs\archive\service.crt",
            "filename": "service.crt",
            "duplicate": True,
            "duplicate_of": r"C:\certs\service.pem",
        },
    ]
    result_response = await client.post(
        "/api/v1/agent/results/filesystem",
        json={
            "run_id": run_id,
            "status": "completed",
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "agent_version": "test",
            "observations": observations,
            "errors": [],
        },
    )
    assert result_response.status_code == 200

    report = (await client.get(f"/api/v1/reports/filesystem/{run_id}")).json()
    assert report["summary"]["certificates_found"] == 2
    assert report["summary"]["unique_certificates"] == 1
    assert report["summary"]["duplicate_observations"] == 1
    stores_edge = next(edge for edge in report["graph"]["edges"] if edge["type"] == "stores")
    assert stores_edge["weight"] == 2

    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["totals"]["total_runs"] == 1
    assert dashboard["totals"]["total_evidence"] == 2


@pytest.mark.asyncio
async def test_tls_report_relationships_and_schedule_crud(api: tuple[Any, Any, Any]) -> None:
    client, app, fake_agent = api
    now = datetime.now(UTC)
    start_response = await client.post(
        "/api/v1/runs/tls",
        json={"duration_seconds": 3, "probe_targets": ["example.com:443"]},
    )
    assert start_response.status_code == 202
    run_id = start_response.json()["id"]
    assert fake_agent.commands[0]["type"] == "tls"

    result = {
        "run_id": run_id,
        "status": "completed",
        "started_at": (now - timedelta(seconds=3)).isoformat(),
        "completed_at": now.isoformat(),
        "agent_version": "test",
        "errors": [],
        "observations": [
            {
                "observed_at": now.isoformat(),
                "source_ip": "127.0.0.1",
                "source_port": 51234,
                "destination_ip": "93.184.216.34",
                "destination_port": 443,
                "direction": "outbound",
                "transport": "TCP",
                "connection_state": "connected",
                "handshake_outcome": "succeeded",
                "hostname": "example.com",
                "sni": "example.com",
                "tls_version": "TLS 1.3",
                "cipher_suite": "TLS_AES_128_GCM_SHA256",
                "peer_certificate_fingerprint": "B" * 64,
                "peer_certificate_subject": "CN=example.com",
                "peer_certificate_issuer": "CN=Example CA",
                "peer_certificate_valid_to": (now + timedelta(days=60)).isoformat(),
                "certificate_status": "valid",
                "pid": 42,
                "process_name": "browser.exe",
                "executable": r"C:\Browser\browser.exe",
                "local_service": "HTTPS",
                "event_count": 4,
                "capture_method": "active_metadata_probe",
                "evidence_confidence": "high",
                "error": "",
            }
        ],
    }
    assert (await client.post("/api/v1/agent/results/tls", json=result)).status_code == 200
    report = (await client.get(f"/api/v1/reports/tls/{run_id}")).json()
    assert report["summary"]["events_observed"] == 4
    assert report["summary"]["unique_endpoints"] == 1
    assert report["summary"]["certificates_observed"] == 1
    assert {edge["type"] for edge in report["graph"]["edges"]} >= {
        "communicates_with",
        "presents",
        "observes",
    }

    schedule_response = await client.post(
        "/api/v1/schedules",
        json={
            "name": "Frequent TLS evidence",
            "scan_type": "tls",
            "interval_minutes": 60,
            "enabled": True,
            "tls": {"duration_seconds": 5, "probe_targets": ["example.com:443"]},
        },
    )
    assert schedule_response.status_code == 201
    schedule_id = schedule_response.json()["id"]
    assert schedule_response.json()["next_run_at"] is not None
    assert len((await client.get("/api/v1/schedules")).json()) == 1

    await app.state.schedule_service._execute(schedule_id)
    scheduled_runs = (await client.get("/api/v1/runs?limit=20")).json()
    assert any(run["trigger_type"] == "scheduled" for run in scheduled_runs)
    assert fake_agent.commands[-1]["type"] == "tls"

    assert (await client.patch(f"/api/v1/schedules/{schedule_id}", json={"enabled": False})).json()[
        "enabled"
    ] is False
    assert (await client.delete(f"/api/v1/schedules/{schedule_id}")).status_code == 204
    assert (await client.get("/api/v1/schedules")).json() == []
