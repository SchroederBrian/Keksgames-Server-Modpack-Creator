from __future__ import annotations

import sys


def main() -> None:
    try:
        from .tui import ServerPackCreatorApp
    except ImportError as exc:
        print("Textual ist nicht installiert. Bitte zuerst ausfuehren:")
        print("  python -m pip install -e .")
        print(f"\nDetails: {exc}")
        raise SystemExit(1) from exc

    ServerPackCreatorApp().run()


if __name__ == "__main__":
    main()
