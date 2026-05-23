from __future__ import annotations

import os
from pathlib import Path


def discover_mod_folders() -> list[Path]:
    roots: list[Path] = []
    appdata = os.getenv("APPDATA")
    localappdata = os.getenv("LOCALAPPDATA")

    for base in filter(None, [appdata, localappdata]):
        base_path = Path(base)
        roots.extend(
            [
                base_path / "com.modrinth.theseus" / "profiles",
                base_path / "ModrinthApp" / "profiles",
                base_path / "modrinth-app" / "profiles",
            ]
        )

    roots.extend([Path.cwd(), Path.cwd() / "profiles", Path.cwd() / "instances"])
    found: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        if root.name == "mods" and root.is_dir():
            _add(root, found, seen)
        if not root.is_dir():
            continue
        for mods_dir in root.glob("**/mods"):
            if mods_dir.is_dir() and any(mods_dir.glob("*.jar")):
                _add(mods_dir, found, seen)
    return found


def _add(path: Path, found: list[Path], seen: set[Path]) -> None:
    resolved = path.resolve()
    if resolved not in seen:
        seen.add(resolved)
        found.append(resolved)
