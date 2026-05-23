from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from typing import Any, TypeVar

from .models import ModCandidate

USER_AGENT = "mc-server-pack-creator/0.1.0"
MODRINTH_API = "https://api.modrinth.com/v2"
CURSEFORGE_API = "https://api.curseforge.com/v1"
T = TypeVar("T")


class ApiError(RuntimeError):
    pass


def lookup_modrinth(candidate: ModCandidate) -> None:
    version = _json_get(f"{MODRINTH_API}/version_file/{candidate.sha1}?algorithm=sha1")
    if not version:
        return

    project = _json_get(f"{MODRINTH_API}/project/{version['project_id']}") or {}
    _apply_modrinth_match(candidate, version, project)


def lookup_modrinth_many(candidates: Iterable[ModCandidate], batch_size: int = 100) -> None:
    candidate_list = list(candidates)
    candidates_by_sha1 = {candidate.sha1: candidate for candidate in candidate_list}
    if not candidates_by_sha1:
        return

    versions_by_hash: dict[str, dict[str, Any]] = {}
    for sha1_batch in _chunks(list(candidates_by_sha1), batch_size):
        data = _json_request(
            f"{MODRINTH_API}/version_files",
            method="POST",
            body={"hashes": sha1_batch, "algorithm": "sha1"},
        )
        if isinstance(data, dict):
            versions_by_hash.update(
                {
                    sha1: version
                    for sha1, version in data.items()
                    if isinstance(version, dict) and sha1 in candidates_by_sha1
                }
            )

    project_ids = {
        version["project_id"]
        for version in versions_by_hash.values()
        if isinstance(version.get("project_id"), str)
    }
    projects_by_id = _lookup_modrinth_projects(project_ids, batch_size)

    for sha1, version in versions_by_hash.items():
        candidate = candidates_by_sha1[sha1]
        project = projects_by_id.get(version.get("project_id"), {})
        _apply_modrinth_match(candidate, version, project)


def _apply_modrinth_match(
    candidate: ModCandidate,
    version: dict[str, Any],
    project: dict[str, Any],
) -> None:
    slug = project.get("slug") or version.get("project_id")
    candidate.source = "modrinth"
    candidate.project_name = project.get("title") or version.get("name")
    candidate.project_id = version.get("project_id")
    candidate.version_id = version.get("id")
    candidate.version_number = version.get("version_number")
    candidate.client_side = project.get("client_side")
    candidate.server_side = project.get("server_side")
    candidate.page_url = f"https://modrinth.com/mod/{slug}/version/{version.get('id')}"
    candidate.download_url = _first_file_url(version, candidate.sha1)
    candidate.raw = {"project": project, "version": version}
    _apply_modrinth_decision(candidate)


def _lookup_modrinth_projects(project_ids: set[str], batch_size: int) -> dict[str, dict[str, Any]]:
    projects_by_id: dict[str, dict[str, Any]] = {}
    for project_batch in _chunks(sorted(project_ids), batch_size):
        query = urllib.parse.urlencode({"ids": json.dumps(project_batch)})
        data = _json_get(f"{MODRINTH_API}/projects?{query}") or []
        if isinstance(data, list):
            projects_by_id.update(
                {
                    project["id"]: project
                    for project in data
                    if isinstance(project, dict) and isinstance(project.get("id"), str)
                }
            )
    return projects_by_id


def lookup_curseforge(candidates: Iterable[ModCandidate], api_key: str | None = None) -> None:
    key = api_key or os.getenv("CURSEFORGE_API_KEY")
    if not key:
        for candidate in candidates:
            _set_search_link(candidate, "CurseForge API-Key fehlt; bitte manuell entscheiden.")
        return

    candidates_by_fp = {candidate.fingerprint: candidate for candidate in candidates}
    if not candidates_by_fp:
        return

    body = {"fingerprints": list(candidates_by_fp)}
    data = _json_request(
        f"{CURSEFORGE_API}/fingerprints",
        method="POST",
        body=body,
        headers={"x-api-key": key},
    )
    matches = (data or {}).get("data", {}).get("exactMatches", [])
    mod_ids: set[int] = set()

    for match in matches:
        file_data = match.get("file") or {}
        fingerprint = int(file_data.get("fileFingerprint") or match.get("id") or 0)
        candidate = candidates_by_fp.get(fingerprint)
        if not candidate:
            continue
        mod_id = file_data.get("modId")
        if mod_id:
            mod_ids.add(int(mod_id))
        candidate.source = "curseforge"
        candidate.project_id = str(mod_id) if mod_id else None
        candidate.file_id = file_data.get("id")
        candidate.version_number = file_data.get("displayName")
        candidate.download_url = file_data.get("downloadUrl")
        candidate.raw["curseforge_file"] = file_data
        candidate.reason = "CurseForge-Match gefunden; Server/Client-Seite bitte bestaetigen."

    mods = _curseforge_mods(mod_ids, key)
    for candidate in candidates_by_fp.values():
        if candidate.source != "curseforge":
            _set_search_link(candidate, "Kein exakter CurseForge-Fingerprint-Match; bitte manuell entscheiden.")
            continue
        mod = mods.get(int(candidate.project_id or 0), {})
        links = mod.get("links") or {}
        candidate.project_name = mod.get("name") or candidate.project_name
        candidate.page_url = links.get("websiteUrl") or _curseforge_fallback_link(candidate)
        candidate.raw["curseforge_project"] = mod


def _apply_modrinth_decision(candidate: ModCandidate) -> None:
    server_side = (candidate.server_side or "").lower()
    client_side = (candidate.client_side or "").lower()
    if server_side in {"required", "optional"}:
        candidate.decision = "server"
        candidate.reason = f"Modrinth markiert Server-Seite als {server_side}."
    elif server_side == "unsupported" and client_side in {"required", "optional"}:
        candidate.decision = "client"
        candidate.reason = "Modrinth markiert diese Mod als clientseitig."
    else:
        candidate.decision = "unknown"
        candidate.reason = "Modrinth-Seitenangabe ist unklar; bitte manuell entscheiden."


def _first_file_url(version: dict[str, Any], sha1: str) -> str | None:
    files = version.get("files") or []
    for file_data in files:
        if (file_data.get("hashes") or {}).get("sha1") == sha1:
            return file_data.get("url")
    for file_data in files:
        if file_data.get("primary"):
            return file_data.get("url")
    return files[0].get("url") if files else None


def _curseforge_mods(mod_ids: set[int], api_key: str) -> dict[int, dict[str, Any]]:
    if not mod_ids:
        return {}
    data = _json_request(
        f"{CURSEFORGE_API}/mods",
        method="POST",
        body={"modIds": sorted(mod_ids)},
        headers={"x-api-key": api_key},
    )
    return {int(mod["id"]): mod for mod in (data or {}).get("data", []) if mod.get("id")}


def _set_search_link(candidate: ModCandidate, reason: str) -> None:
    candidate.source = "unknown"
    candidate.reason = reason
    candidate.page_url = _curseforge_fallback_link(candidate)


def _curseforge_fallback_link(candidate: ModCandidate) -> str:
    query = candidate.metadata.name or candidate.metadata.mod_id or candidate.path.stem
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.curseforge.com/minecraft/search?class=mc-mods&search={encoded}"


def _json_get(url: str) -> Any:
    return _json_request(url, method="GET")


def _chunks(items: list[T], size: int) -> Iterable[list[T]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _json_request(
    url: str,
    *,
    method: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        **(headers or {}),
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise ApiError(f"{url} -> HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApiError(f"{url} -> {exc}") from exc
