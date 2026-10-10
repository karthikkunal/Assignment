from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScanType = Literal["filesystem", "tls"]
RunStatus = Literal["queued", "running", "completed", "partial", "failed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilesystemRunRequest(StrictModel):
    roots: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("roots")
    @classmethod
    def clean_roots(cls, roots: list[str]) -> list[str]:
        return unique_nonempty(roots)


class TLSRunRequest(StrictModel):
    duration_seconds: int = Field(default=15, ge=1, le=300)
    probe_targets: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("probe_targets")
    @classmethod
    def clean_targets(cls, targets: list[str]) -> list[str]:
        return unique_nonempty(targets)


class AgentStatusUpdate(StrictModel):
    status: RunStatus
    timestamp: datetime
    message: str = Field(default="", max_length=2000)


class ScanError(StrictModel):
    path: str = ""
    message: str


class CertificateObservationIn(StrictModel):
    path: str
    filename: str
    format: str
    discovered_at: datetime
    scan_root: str
    fingerprint_sha256: str = ""
    serial_number: str = ""
    subject: str = ""
    issuer: str = ""
    san_entries: list[str] = Field(default_factory=list)
    chain_position: int = 0
    public_key_algorithm: str = ""
    public_key_size: int = 0
    signature_algorithm: str = ""
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    days_to_expiry: int | None = None
    validity_status: str
    owner_process: str = "unavailable"
    parsing_status: str
    access_error: str = ""
    evidence_confidence: str
    duplicate: bool = False
    duplicate_of: str = ""


class FilesystemResultIn(StrictModel):
    run_id: str
    status: Literal["completed", "partial", "failed"]
    started_at: datetime
    completed_at: datetime
    agent_version: str
    observations: list[CertificateObservationIn]
    errors: list[ScanError] = Field(default_factory=list)


class TLSObservationIn(StrictModel):
    observed_at: datetime
    source_ip: str = ""
    source_port: int = 0
    destination_ip: str = ""
    destination_port: int = 0
    direction: str
    transport: str
    connection_state: str
    handshake_outcome: str
    hostname: str = ""
    sni: str = ""
    tls_version: str = ""
    cipher_suite: str = ""
    peer_certificate_fingerprint: str = ""
    peer_certificate_subject: str = ""
    peer_certificate_issuer: str = ""
    peer_certificate_valid_to: datetime | None = None
    certificate_status: str = ""
    pid: int = 0
    process_name: str = ""
    executable: str = ""
    local_service: str = ""
    event_count: int = Field(default=1, ge=0)
    capture_method: str
    evidence_confidence: str
    error: str = ""


class TLSResultIn(StrictModel):
    run_id: str
    status: Literal["completed", "partial", "failed"]
    started_at: datetime
    completed_at: datetime
    agent_version: str
    observations: list[TLSObservationIn]
    errors: list[ScanError] = Field(default_factory=list)


class ScheduleRequest(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    scan_type: ScanType
    interval_minutes: int = Field(ge=1, le=10080)
    enabled: bool = True
    filesystem: FilesystemRunRequest | None = None
    tls: TLSRunRequest | None = None


def unique_nonempty(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned
