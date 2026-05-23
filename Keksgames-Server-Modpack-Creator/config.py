from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "CURSEFORGE_API_KEY": "",
    "MC_SERVER_PACK_SCAN_WORKERS": 8,
    "SERVER_SIDE_DIRS": [
        "config",
        "defaultconfigs",
        "kubejs",
        "scripts",
        "datapacks",
        "openloader",
        "configureddefaults",
        "patchouli_books",
    ],
    "SERVER_SIDE_FILES": [
        "server.properties",
        "allowlist.json",
        "whitelist.json",
    ],
    "USER_AGENT": "mc-server-pack-creator/0.1.0",
    "MODRINTH_API": "https://api.modrinth.com/v2",
    "CURSEFORGE_API": "https://api.curseforge.com/v1",
    "DEFAULT_XMS": "2G",
    "DEFAULT_XMX": "6G",
    "START_COMMAND": "java -Xms{xms} -Xmx{xmx} -jar server.jar nogui",
}


class Config:
    def __init__(self, config_path: Path | str | None = None) -> None:
        self._settings = DEFAULT_CONFIG.copy()

        # Load from file if specified, or search in the parent directory of __file__
        # (which is Keksgames-Server-Modpack-Creator), or look for config.json in the current working directory
        cwd_config = Path("config.json")
        pkg_config = Path(__file__).resolve().parent.parent / "config.json"

        if config_path is not None:
            self.load_from_file(Path(config_path))
        elif cwd_config.is_file():
            self.load_from_file(cwd_config)
        elif pkg_config.is_file():
            self.load_from_file(pkg_config)

        self._load_from_env()

    def load_from_file(self, path: Path) -> None:
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k in self._settings:
                            expected_type = type(DEFAULT_CONFIG[k])
                            if isinstance(v, expected_type):
                                self._settings[k] = v
                            else:
                                try:
                                    if expected_type is int:
                                        self._settings[k] = int(v)
                                    elif expected_type is list:
                                        self._settings[k] = list(v)
                                    else:
                                        self._settings[k] = str(v)
                                except Exception:
                                    pass
        except Exception as e:
            print(f"Fehler beim Laden der Konfiguration aus {path}: {e}")

    def _load_from_env(self) -> None:
        for key in self._settings:
            env_val = os.getenv(key)
            if env_val is not None:
                expected_type = type(DEFAULT_CONFIG[key])
                if expected_type is int:
                    try:
                        self._settings[key] = int(env_val)
                    except ValueError:
                        pass
                elif expected_type is list:
                    self._settings[key] = [item.strip() for item in env_val.split(",")]
                else:
                    self._settings[key] = env_val

    @property
    def curseforge_api_key(self) -> str:
        return self._settings["CURSEFORGE_API_KEY"]

    @property
    def scan_workers(self) -> int:
        return self._settings["MC_SERVER_PACK_SCAN_WORKERS"]

    @property
    def server_side_dirs(self) -> list[str]:
        return self._settings["SERVER_SIDE_DIRS"]

    @property
    def server_side_files(self) -> list[str]:
        return self._settings["SERVER_SIDE_FILES"]

    @property
    def user_agent(self) -> str:
        return self._settings["USER_AGENT"]

    @property
    def modrinth_api(self) -> str:
        return self._settings["MODRINTH_API"]

    @property
    def curseforge_api(self) -> str:
        return self._settings["CURSEFORGE_API"]

    @property
    def default_xms(self) -> str:
        return self._settings["DEFAULT_XMS"]

    @property
    def default_xmx(self) -> str:
        return self._settings["DEFAULT_XMX"]

    @property
    def start_command(self) -> str:
        return self._settings["START_COMMAND"]


config = Config()
