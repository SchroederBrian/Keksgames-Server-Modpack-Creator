from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import config
from .models import ModCandidate


def create_server_pack(source_mod_folder: Path, output_folder: Path, candidates: list[ModCandidate]) -> Path:
    output_folder.mkdir(parents=True, exist_ok=True)
    mods_output = output_folder / "mods"
    if mods_output.exists():
        shutil.rmtree(mods_output)
    mods_output.mkdir(exist_ok=True)

    for candidate in candidates:
        if candidate.decision == "server":
            shutil.copy2(candidate.path, mods_output / candidate.filename)

    instance_root = source_mod_folder.parent
    copied_paths: list[str] = []
    for dirname in config.server_side_dirs:
        source = instance_root / dirname
        if source.is_dir():
            destination = output_folder / dirname
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            copied_paths.append(dirname)

    for filename in config.server_side_files:
        source = instance_root / filename
        if source.is_file():
            shutil.copy2(source, output_folder / filename)
            copied_paths.append(filename)

    _write_manifest(output_folder, source_mod_folder, candidates, copied_paths)
    _write_start_scripts(output_folder)
    _write_readme(output_folder, candidates, copied_paths)
    return output_folder


def _write_manifest(
    output_folder: Path,
    source_mod_folder: Path,
    candidates: list[ModCandidate],
    copied_paths: list[str],
) -> None:
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_mod_folder": str(source_mod_folder),
        "included_mods": sum(1 for candidate in candidates if candidate.decision == "server"),
        "excluded_mods": sum(1 for candidate in candidates if candidate.decision != "server"),
        "copied_server_paths": copied_paths,
        "mods": [candidate.as_report_row() for candidate in candidates],
    }
    (output_folder / "server-pack-report.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
        errors="backslashreplace",
    )


def _write_start_scripts(output_folder: Path) -> None:
    cmd = config.start_command.format(xms=config.default_xms, xmx=config.default_xmx)
    (output_folder / "start-server.ps1").write_text(
        f"$ErrorActionPreference = 'Stop'\n{cmd}\n",
        encoding="utf-8",
    )
    (output_folder / "start-server.sh").write_text(
        f"#!/usr/bin/env sh\n{cmd}\n",
        encoding="utf-8",
    )


def _write_readme(output_folder: Path, candidates: list[ModCandidate], copied_paths: list[str]) -> None:
    included = [candidate for candidate in candidates if candidate.decision == "server"]
    excluded = [candidate for candidate in candidates if candidate.decision != "server"]
    lines = [
        "# Server Modpack",
        "",
        "Lege die passende Loader-Serverdatei als `server.jar` in diesen Ordner und starte dann eines der Startskripte.",
        "",
        f"Inkludierte Mods: {len(included)}",
        f"Ausgeschlossene/uebersprungene Mods: {len(excluded)}",
        "",
        "Kopierte Server-Dateien:",
        *(f"- {path}" for path in copied_paths),
        "",
        "Details stehen in `server-pack-report.json`.",
    ]
    (output_folder / "README.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        errors="backslashreplace",
    )
