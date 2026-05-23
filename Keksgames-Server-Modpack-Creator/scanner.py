from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from pathlib import Path

from .hashes import curseforge_fingerprint, sha1_file
from .jar_meta import read_jar_metadata
from .config import config
from .models import ModCandidate
from .providers import ApiError, lookup_curseforge, lookup_modrinth, lookup_modrinth_many

StatusCallback = Callable[[str], None]


def scan_mod_folder(
    mod_folder: Path,
    status: StatusCallback | None = None,
    max_workers: int | None = None,
) -> list[ModCandidate]:
    emit = status or (lambda _message: None)
    jar_paths = sorted(mod_folder.glob("*.jar"), key=lambda path: path.name.lower())
    workers = _worker_count(len(jar_paths), max_workers)
    candidates: list[ModCandidate | None] = [None] * len(jar_paths)
    emit(f"{len(jar_paths)} JAR-Dateien gefunden; lese mit {workers} parallelen Workern.")

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jar-scan") as executor:
        futures = {
            executor.submit(_read_candidate, jar_path): index
            for index, jar_path in enumerate(jar_paths)
        }
        for done_count, future in enumerate(as_completed(futures), start=1):
            index = futures[future]
            candidate = future.result()
            candidates[index] = candidate
            emit(f"[{done_count}/{len(jar_paths)}] gelesen: {candidate.filename}")

    resolved_candidates = [candidate for candidate in candidates if candidate is not None]
    if not resolved_candidates:
        return []

    emit("Frage Modrinth in Batches ab.")
    try:
        lookup_modrinth_many(resolved_candidates)
    except ApiError as exc:
        emit(f"Batch-Lookup fehlgeschlagen, versuche parallelen Einzel-Lookup: {exc}")
        _lookup_modrinth_individually(resolved_candidates, workers, emit)

    unmatched = [candidate for candidate in resolved_candidates if candidate.source != "modrinth"]
    if unmatched:
        emit(f"{len(unmatched)} Mods nicht auf Modrinth gefunden; pruefe CurseForge/Fallback.")
        try:
            lookup_curseforge(unmatched)
        except ApiError as exc:
            for candidate in unmatched:
                if candidate.source != "curseforge":
                    candidate.reason = f"CurseForge-Lookup fehlgeschlagen: {exc}"

    return resolved_candidates


def needs_manual_decision(candidate: ModCandidate) -> bool:
    return candidate.decision == "unknown" or candidate.source in {"curseforge", "unknown"}


def _read_candidate(jar_path: Path) -> ModCandidate:
    return ModCandidate(
        path=jar_path,
        sha1=sha1_file(jar_path),
        fingerprint=curseforge_fingerprint(jar_path),
        metadata=read_jar_metadata(jar_path),
    )


def _lookup_modrinth_individually(
    candidates: list[ModCandidate],
    workers: int,
    emit: StatusCallback,
) -> None:
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="modrinth") as executor:
        futures = {executor.submit(lookup_modrinth, candidate): candidate for candidate in candidates}
        for done_count, future in enumerate(as_completed(futures), start=1):
            candidate = futures[future]
            try:
                future.result()
            except ApiError as exc:
                candidate.reason = f"Modrinth-Lookup fehlgeschlagen: {exc}"
            emit(f"[{done_count}/{len(candidates)}] Modrinth: {candidate.filename}")


def _worker_count(item_count: int, configured: int | None) -> int:
    if item_count <= 0:
        return 1
    raw = configured or config.scan_workers
    return max(1, min(raw, item_count))
