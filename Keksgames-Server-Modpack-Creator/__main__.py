from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    react_cli = project_root / "src" / "cli.js"
    node = shutil.which("node")

    if node is None:
        print("Node.js wurde nicht gefunden. Fuer die React-TUI bitte Node.js installieren.")
        raise SystemExit(1)

    if not react_cli.is_file():
        print(f"React-TUI nicht gefunden: {react_cli}")
        raise SystemExit(1)

    env = {**dict(os.environ), "PYTHON": sys.executable}
    completed = subprocess.run([node, str(react_cli)], cwd=project_root, env=env, check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
