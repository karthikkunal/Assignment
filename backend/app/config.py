from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QG_",
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "QuantumGenie Discovery"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8765, ge=1, le=65535)
    database_path: Path = PROJECT_ROOT / "data" / "quantumgenie.db"
    migrations_path: Path = BACKEND_ROOT / "migrations"
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    agent_url: str = "http://127.0.0.1:8766"
    agent_token: str = ""
    default_scan_roots: str = ""
    default_tls_duration_seconds: int = Field(default=15, ge=1, le=300)
    default_probe_targets: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @property
    def scan_roots(self) -> list[str]:
        return split_setting(self.default_scan_roots, ";")

    @property
    def probe_targets(self) -> list[str]:
        return split_setting(self.default_probe_targets, ",")

    @property
    def allowed_origins(self) -> list[str]:
        return split_setting(self.cors_origins, ",")


def split_setting(value: str, separator: str) -> list[str]:
    return [item.strip() for item in value.split(separator) if item.strip()]
