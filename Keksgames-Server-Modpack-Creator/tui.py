from __future__ import annotations

import datetime as dt
import threading
import webbrowser
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, RichLog, Static

from .discovery import discover_mod_folders
from .models import ModCandidate
from .packer import create_server_pack
from .scanner import needs_manual_decision, scan_mod_folder


class PathScreen(Screen[None]):
    CSS = """
    PathScreen {
        background: #10131a;
    }
    #shell {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }
    #title {
        text-style: bold;
        color: #f4f0d9;
        margin-bottom: 1;
    }
    #form {
        border: solid #44546a;
        padding: 1 2;
        height: auto;
        background: #151b24;
    }
    Input {
        margin-bottom: 1;
    }
    DataTable {
        height: 1fr;
        margin-top: 1;
        border: solid #44546a;
    }
    Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        candidates = discover_mod_folders()
        default_mods = str(candidates[0]) if candidates else str(Path.cwd() / "mods")
        default_output = str(Path.cwd() / f"server-pack-{dt.datetime.now():%Y%m%d-%H%M}")
        with Vertical(id="shell"):
            yield Header(show_clock=True)
            yield Static("Minecraft Server Pack Creator", id="title")
            with Container(id="form"):
                yield Label("Mods-Ordner")
                yield Input(default_mods, id="mods")
                yield Label("Ausgabeordner")
                yield Input(default_output, id="output")
                with Horizontal():
                    yield Button("Scan starten", id="start", variant="primary")
                    yield Button("Beenden", id="quit")
            yield Label("Gefundene Modrinth/Launcher-Profile")
            table = DataTable(id="profiles")
            table.add_column("Profil-Mods-Ordner")
            for path in candidates:
                table.add_row(str(path))
            yield table
            yield Footer()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = event.data_table.get_row(event.row_key)
        self.query_one("#mods", Input).value = str(row[0])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
            return
        if event.button.id != "start":
            return

        mods = Path(self.query_one("#mods", Input).value).expanduser()
        output = Path(self.query_one("#output", Input).value).expanduser()
        if not mods.is_dir():
            self.notify("Mods-Ordner existiert nicht.", severity="error")
            return
        if mods.name.lower() != "mods":
            self.notify("Bitte den eigentlichen mods-Ordner waehlen.", severity="warning")
        self.app.mod_folder = mods.resolve()
        self.app.output_folder = output.resolve()
        self.app.push_screen(ScanScreen())


class ScanScreen(Screen[None]):
    CSS = """
    ScanScreen {
        background: #10131a;
    }
    #scan {
        padding: 1 2;
    }
    #headline {
        text-style: bold;
        color: #f4f0d9;
        margin-bottom: 1;
    }
    RichLog {
        height: 1fr;
        border: solid #44546a;
        background: #151b24;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="scan"):
            yield Header(show_clock=True)
            yield Static("Scan laeuft", id="headline")
            yield RichLog(id="log", markup=True, wrap=True)
            yield Footer()

    def on_mount(self) -> None:
        self.scan_log = self.query_one("#log", RichLog)
        thread = threading.Thread(target=self._scan, daemon=True)
        thread.start()

    def _scan(self) -> None:
        def status(message: str) -> None:
            self.app.call_from_thread(self.scan_log.write, Text(message))

        try:
            candidates = scan_mod_folder(self.app.mod_folder, status)
        except Exception as exc:  # noqa: BLE001 - surface unexpected scan errors in the TUI.
            self.app.call_from_thread(self.notify, f"Scan fehlgeschlagen: {exc}", severity="error")
            return
        self.app.candidates = candidates
        self.app.manual_queue = [candidate for candidate in candidates if needs_manual_decision(candidate)]
        self.app.manual_total = len(self.app.manual_queue)
        self.app.call_from_thread(self._continue)

    def _continue(self) -> None:
        if self.app.manual_queue:
            self.app.push_screen(DecisionScreen())
        else:
            self.app.push_screen(BuildScreen())


class DecisionScreen(Screen[None]):
    CSS = """
    DecisionScreen {
        background: #10131a;
    }
    #decision {
        padding: 1 2;
    }
    #card {
        border: solid #44546a;
        padding: 1 2;
        background: #151b24;
        height: auto;
    }
    #name {
        text-style: bold;
        color: #f4f0d9;
        margin-bottom: 1;
    }
    #url {
        color: #8fd3ff;
        margin: 1 0;
    }
    Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="decision"):
            yield Header(show_clock=True)
            with Container(id="card"):
                yield Static("", id="name")
                yield Static("", id="meta")
                yield Static("", id="reason")
                yield Static("", id="url")
                with Horizontal():
                    yield Button("Server", id="server", variant="success")
                    yield Button("Client", id="client", variant="warning")
                    yield Button("Skip", id="skip")
                    yield Button("Link oeffnen", id="open")
            yield Footer()

    def on_mount(self) -> None:
        self._render_current()

    @property
    def current(self) -> ModCandidate:
        return self.app.manual_queue[0]

    def _render_current(self) -> None:
        candidate = self.current
        index = self.app.manual_total - len(self.app.manual_queue) + 1
        total = self.app.manual_total
        self.query_one("#name", Static).update(f"{candidate.display_name} ({index}/{total})")
        self.query_one("#meta", Static).update(
            f"Datei: {candidate.filename}\n"
            f"Version: {candidate.display_version}\n"
            f"Quelle: {candidate.source}"
        )
        self.query_one("#reason", Static).update(candidate.reason)
        self.query_one("#url", Static).update(candidate.page_url or "Kein Link gefunden.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        candidate = self.current
        if event.button.id == "open":
            if candidate.page_url:
                webbrowser.open(candidate.page_url)
            return

        if event.button.id in {"server", "client", "skip"}:
            candidate.decision = event.button.id
            candidate.reason = f"Manuell im TUI als {event.button.id} markiert."
            self.app.manual_queue.pop(0)
            if self.app.manual_queue:
                self._render_current()
            else:
                self.app.push_screen(BuildScreen())


class BuildScreen(Screen[None]):
    CSS = """
    BuildScreen {
        background: #10131a;
    }
    #build {
        padding: 1 2;
    }
    #headline {
        text-style: bold;
        color: #f4f0d9;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="build"):
            yield Header(show_clock=True)
            yield Static("Serverpack wird gebaut", id="headline")
            yield RichLog(id="log", markup=True, wrap=True)
            yield Footer()

    def on_mount(self) -> None:
        self.build_log = self.query_one("#log", RichLog)
        thread = threading.Thread(target=self._build, daemon=True)
        thread.start()

    def _build(self) -> None:
        self.app.call_from_thread(self.build_log.write, Text(f"Ausgabe: {self.app.output_folder}"))
        try:
            create_server_pack(self.app.mod_folder, self.app.output_folder, self.app.candidates)
        except Exception as exc:  # noqa: BLE001 - surface unexpected pack errors in the TUI.
            self.app.call_from_thread(self.notify, f"Build fehlgeschlagen: {exc}", severity="error")
            return
        self.app.call_from_thread(self.app.push_screen, ReportScreen())


class ReportScreen(Screen[None]):
    CSS = """
    ReportScreen {
        background: #10131a;
    }
    #report {
        padding: 1 2;
    }
    #headline {
        text-style: bold;
        color: #f4f0d9;
        margin-bottom: 1;
    }
    DataTable {
        height: 1fr;
        border: solid #44546a;
        background: #151b24;
    }
    Button {
        margin-top: 1;
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        included = sum(1 for candidate in self.app.candidates if candidate.decision == "server")
        excluded = len(self.app.candidates) - included
        with Vertical(id="report"):
            yield Header(show_clock=True)
            yield Static(f"Fertig: {included} Server-Mods, {excluded} ausgeschlossen", id="headline")
            table = DataTable(id="mods")
            for column in ("Entscheidung", "Quelle", "Name", "Version", "Datei"):
                table.add_column(column)
            for candidate in self.app.candidates:
                table.add_row(
                    candidate.decision,
                    candidate.source,
                    candidate.display_name,
                    candidate.display_version,
                    candidate.filename,
                )
            yield table
            with Horizontal():
                yield Button("Ordner oeffnen", id="open", variant="primary")
                yield Button("Beenden", id="quit")
            yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open":
            webbrowser.open(str(self.app.output_folder))
        if event.button.id == "quit":
            self.app.exit()


class ServerPackCreatorApp(App[None]):
    TITLE = "Minecraft Server Pack Creator"
    BINDINGS = [("q", "quit", "Quit")]

    mod_folder: Path
    output_folder: Path
    candidates: list[ModCandidate]
    manual_queue: list[ModCandidate]
    manual_total: int

    def on_mount(self) -> None:
        self.candidates = []
        self.manual_queue = []
        self.manual_total = 0
        self.push_screen(PathScreen())
