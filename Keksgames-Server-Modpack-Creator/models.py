from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Decision = Literal["server", "client", "skip", "unknown"]
Source = Literal["modrinth", "curseforge", "local", "unknown"]


@dataclass(slots=True)
class JarMetadata:
    mod_id: str | None = None
    name: str | None = None
    version: str | None = None
    loader: str | None = None
    description: str | None = None


@dataclass(slots=True)
class ModCandidate:
    path: Path
    sha1: str
    fingerprint: int
    metadata: JarMetadata = field(default_factory=JarMetadata)
    source: Source = "unknown"
    project_name: str | None = None
    project_id: str | None = None
    version_id: str | None = None
    version_number: str | None = None
    file_id: str | int | None = None
    page_url: str | None = None
    download_url: str | None = None
    client_side: str | None = None
    server_side: str | None = None
    decision: Decision = "unknown"
    reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def display_name(self) -> str:
        return self.project_name or self.metadata.name or self.metadata.mod_id or self.filename

    @property
    def display_version(self) -> str:
        return self.version_number or self.metadata.version or "?"

    def as_report_row(self) -> dict[str, Any]:
        return {
            "file": self.filename,
            "name": self.display_name,
            "version": self.display_version,
            "source": self.source,
            "decision": self.decision,
            "client_side": self.client_side,
            "server_side": self.server_side,
            "page_url": self.page_url,
            "sha1": self.sha1,
            "fingerprint": self.fingerprint,
            "reason": self.reason,
        }
