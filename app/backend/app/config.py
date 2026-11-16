"""Settings, read from the repo-root .env (ARCHEION_* variables) with safe defaults."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import REPO_ROOT
from .services.roots import Roots, parse_roots


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARCHEION_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 20300
    frontend_port: int = 20301
    # Relative paths are resolved against the repo root.
    db_path: str = "app/backend/data/archeion.db"
    session_idle_hours: float = 12
    session_max_days: float = 7
    # An optional folder holding projects (relative to the repo root), the root named
    # "workspace": pages without `root:` resolve inside it (ADR 0006). Empty by default, so
    # nothing is granted until you add a root (ADR 0012).
    workspace_root: str = ""
    # More folders projects may live in, as name=folder;name=folder (ADR 0008). A registry
    # page picks one with `root: <name>`. Machine-specific, so only ever set in .env.
    roots: str = ""
    # The private registry folder (gitignored; setup.bat creates it from registry.example/).
    registry_dir: str = "registry"
    # Code study snapshots kept per project in registry/studies/ (ADR 0019).
    study_keep: int = 10

    # Not meant for .env: tests point these at a temporary repo.
    repo_root: Path = REPO_ROOT
    watch_docs: bool = True
    feedback_poll_seconds: float = 2.0
    # On-demand Claude (ADR 0020): how often the backend checks for waiting messages.
    watch_responder: bool = True
    responder_poll_seconds: float = 3.0
    login_max_failures: int = 5
    login_window_seconds: int = 600
    login_fail_delay_seconds: float = 0.5
    extra_allowed_hosts: list[str] = []

    @cached_property
    def docs_root(self) -> Path:
        return (self.repo_root / "docs").resolve()

    @cached_property
    def registry_root(self) -> Path:
        p = Path(self.registry_dir)
        return (p if p.is_absolute() else (self.repo_root / p)).resolve()

    @cached_property
    def workspace_dir(self) -> Path | None:
        if not self.workspace_root.strip():
            return None
        p = Path(self.workspace_root)
        return (p if p.is_absolute() else (self.repo_root / p)).resolve()

    @cached_property
    def project_roots(self) -> Roots:
        return parse_roots(self.roots, self.repo_root, self.workspace_dir)

    @cached_property
    def db_file(self) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else (self.repo_root / p)

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = {"127.0.0.1", "localhost", self.host, *self.extra_allowed_hosts}
        hosts.discard("0.0.0.0")
        return sorted(hosts)

    @property
    def allowed_origins(self) -> set[str]:
        origins: set[str] = set()
        for host in self.allowed_hosts:
            for port in (self.frontend_port, self.port):
                origins.add(f"http://{host}:{port}")
        return origins


def read_version(repo_root: Path = REPO_ROOT) -> str:
    try:
        return (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
