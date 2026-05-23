from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from .discovery import discover_mod_folders
from .models import JarMetadata, ModCandidate
from .packer import create_server_pack
from .scanner import needs_manual_decision, scan_mod_folder

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    command = args[0] if args else "discover"

    if command == "discover":
        _discover()
    elif command == "scan":
        _scan(Path(args[1]))
    elif command == "build":
        _build(Path(args[1]), Path(args[2]))
    else:
        raise SystemExit(f"Unknown backend command: {command}")


def _discover() -> None:
    profiles = discover_mod_folders()
    default_mods = profiles[0] if profiles else Path.cwd() / "mods"
    default_output = Path.cwd() / f"server-pack-{dt.datetime.now():%Y%m%d-%H%M}"
    json.dump(
        {
            "profiles": [str(path) for path in profiles],
            "default_mods": str(default_mods),
            "default_output": str(default_output),
        },
        sys.stdout,
        ensure_ascii=True,
    )
    sys.stdout.write("\n")


def _scan(mod_folder: Path) -> None:
    def status(message: str) -> None:
        _emit({"type": "status", "message": message})

    candidates = scan_mod_folder(mod_folder, status)
    _emit(
        {
            "type": "result",
            "candidates": [_candidate_to_json(candidate) for candidate in candidates],
            "manual_count": sum(1 for candidate in candidates if needs_manual_decision(candidate)),
        }
    )


def _build(mod_folder: Path, output_folder: Path) -> None:
    payload = json.load(sys.stdin)
    candidates = [_candidate_from_json(item) for item in payload]
    _emit({"type": "status", "message": f"Baue Serverpack in {output_folder}"})
    create_server_pack(mod_folder, output_folder, candidates)
    _emit({"type": "result", "output_folder": str(output_folder)})


def _candidate_to_json(candidate: ModCandidate) -> dict[str, Any]:
    return {
        "file": candidate.filename,
        "path": str(candidate.path),
        "sha1": candidate.sha1,
        "fingerprint": candidate.fingerprint,
        "metadata": {
            "mod_id": candidate.metadata.mod_id,
            "name": candidate.metadata.name,
            "version": candidate.metadata.version,
            "loader": candidate.metadata.loader,
            "description": candidate.metadata.description,
        },
        "source": candidate.source,
        "name": candidate.display_name,
        "project_name": candidate.project_name,
        "project_id": candidate.project_id,
        "version_id": candidate.version_id,
        "version": candidate.display_version,
        "version_number": candidate.version_number,
        "file_id": candidate.file_id,
        "page_url": candidate.page_url,
        "download_url": candidate.download_url,
        "client_side": candidate.client_side,
        "server_side": candidate.server_side,
        "decision": candidate.decision,
        "reason": candidate.reason,
    }


def _candidate_from_json(data: dict[str, Any]) -> ModCandidate:
    metadata = data.get("metadata") or {}
    candidate = ModCandidate(
        path=Path(data["path"]),
        sha1=data["sha1"],
        fingerprint=int(data["fingerprint"]),
        metadata=JarMetadata(
            mod_id=metadata.get("mod_id"),
            name=metadata.get("name"),
            version=metadata.get("version"),
            loader=metadata.get("loader"),
            description=metadata.get("description"),
        ),
    )
    candidate.source = data.get("source") or "unknown"
    candidate.project_name = data.get("project_name") or data.get("name")
    candidate.project_id = data.get("project_id")
    candidate.version_id = data.get("version_id")
    candidate.version_number = data.get("version_number") or data.get("version")
    candidate.file_id = data.get("file_id")
    candidate.page_url = data.get("page_url")
    candidate.download_url = data.get("download_url")
    candidate.client_side = data.get("client_side")
    candidate.server_side = data.get("server_side")
    candidate.decision = data.get("decision") or "unknown"
    candidate.reason = data.get("reason") or ""
    return candidate


def _emit(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=True) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
