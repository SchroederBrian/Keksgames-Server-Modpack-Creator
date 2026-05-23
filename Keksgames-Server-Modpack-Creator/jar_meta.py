from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from .models import JarMetadata


def read_jar_metadata(path: Path) -> JarMetadata:
    try:
        with zipfile.ZipFile(path) as jar:
            names = set(jar.namelist())
            if "fabric.mod.json" in names:
                return _fabric_metadata(_read_json(jar, "fabric.mod.json"))
            if "quilt.mod.json" in names:
                return _quilt_metadata(_read_json(jar, "quilt.mod.json"))
            for toml_name in ("META-INF/mods.toml", "META-INF/neoforge.mods.toml"):
                if toml_name in names:
                    return _forge_metadata(jar.read(toml_name).decode("utf-8", errors="replace"))
            if "mcmod.info" in names:
                return _mcmod_info(_read_json(jar, "mcmod.info"))
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return JarMetadata()
    return JarMetadata()


def _read_json(jar: zipfile.ZipFile, name: str) -> Any:
    return json.loads(jar.read(name).decode("utf-8", errors="replace"))


def _fabric_metadata(data: dict[str, Any]) -> JarMetadata:
    contact = data.get("contact") or {}
    return JarMetadata(
        mod_id=data.get("id"),
        name=data.get("name"),
        version=data.get("version"),
        loader="fabric",
        description=data.get("description") or contact.get("homepage"),
    )


def _quilt_metadata(data: dict[str, Any]) -> JarMetadata:
    quilt_loader = data.get("quilt_loader") or {}
    metadata = quilt_loader.get("metadata") or {}
    return JarMetadata(
        mod_id=quilt_loader.get("id"),
        name=metadata.get("name"),
        version=quilt_loader.get("version"),
        loader="quilt",
        description=metadata.get("description"),
    )


def _forge_metadata(text: str) -> JarMetadata:
    block = _first_mods_toml_block(text)
    mod_id = _toml_string(block, "modId") or _toml_string(text, "modId")
    name = _toml_string(block, "displayName") or _toml_string(text, "displayName")
    version = _toml_string(block, "version") or _toml_string(text, "version")
    loader = "neoforge" if "neoForge" in text or "neoforge" in text.lower() else "forge"
    return JarMetadata(mod_id=mod_id, name=name, version=version, loader=loader)


def _first_mods_toml_block(text: str) -> str:
    match = re.search(r"\[\[mods]](?P<body>.*?)(?:\n\[|\Z)", text, flags=re.DOTALL)
    return match.group("body") if match else text


def _toml_string(text: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*['\"](?P<value>.*?)['\"]", text, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group("value").strip()
    return None if value.startswith("${") else value


def _mcmod_info(data: Any) -> JarMetadata:
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return JarMetadata()
    return JarMetadata(
        mod_id=data.get("modid"),
        name=data.get("name"),
        version=data.get("version"),
        loader="forge",
        description=data.get("description"),
    )
