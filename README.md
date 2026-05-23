# 🎮 Keksgames Server Modpack Creator

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![React TUI](https://img.shields.io/badge/UI-React%20Ink-61dafb.svg)](https://github.com/vadimdemedes/ink)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Ein intelligentes, interaktives **TUI (Terminal User Interface)**-Tool für Minecraft, das deinen lokalen `mods`-Ordner eines Launcher-Profils scannt, Mod-Metadaten analysiert und daraus vollautomatisch ein lauffähiges, bereinigtes **serverseitiges Modpack** erstellt.

Kein manuelles Aussortieren von clientseitigen Mods (wie HUDs, Shadern oder Minimaps) mehr!

---

## ✨ Features

- **🔍 Automatische Profil-Erkennung**: Findet typische Modrinth-App-Profile in deinen AppData-Pfaden vollautomatisch.
- **📦 Lokale JAR-Analyse**: Liest die Metadaten (`fabric.mod.json`, `quilt.mod.json`, `mods.toml`, `mcmod.info`) der lokalen `.jar`-Dateien direkt aus, um Loader-Typ, Versionen und Mod-IDs zu bestimmen.
- **⚡ Blitzschneller Parallel-Scan**: Analysiert mehrere Mods gleichzeitig über einen konfigurierbaren ThreadPool-Scanner (Standard: 8 parallele Worker).
- **🌐 Modrinth API Integration**: Matcht Mods per SHA-1-Hash auf Modrinth und übernimmt automatisch deren Angaben zu `client_side` und `server_side`.
- **🔥 CurseForge API Integration**: Matcht Mods per CurseForge-Fingerprint (MurmurHash2), wenn ein `CURSEFORGE_API_KEY` hinterlegt ist.
- **🖥️ React TUI (Terminal-Oberfläche)**: Zeigt CurseForge- oder unklare Mods übersichtlich mit direkten Suchlinks an, sodass du per Tastatur entscheiden kannst, ob die Mod auf den Server gehört.
- **📁 Server-Konfigurations-Kopierer**: Erkennt und kopiert serverrelevante Ordner (`config`, `defaultconfigs`, `kubejs`, `scripts`, `datapacks`, `openloader` etc.) und Dateien (`server.properties`, `whitelist.json`) aus dem Instanz-Ordner.
- **📄 Automatischer Report & Skripte**: Generiert einen detaillierten Report im JSON-Format (`server-pack-report.json`) sowie lauffähige Startskripte (`start-server.ps1` / `start-server.sh`) und eine README im Ausgabeordner.

---

## ⚙️ Voraussetzungen

- **Python**: Version **3.11 oder höher**
- **Node.js + npm**: für die React/Ink Terminal-Oberfläche
- **Betriebssystem**: Getestet auf Windows

---

## 🚀 Installation & Start

### Option A: Entwicklungsmodus (Empfohlen)

Klone dieses Repository und installiere es im editierbaren Modus:

```powershell
# Repository klonen (oder herunterladen)
git clone https://github.com/SchroederBrian/Keksgames-Server-Modpack-Creator.git
cd Keksgames-Server-Modpack-Creator

# Paket editierbar installieren
python -m pip install -e .
npm install

# Tool starten
mc-server-pack
```

### Option B: Direkt ausführen ohne Installation

Falls du das Tool nicht global installieren möchtest:

```powershell
npm install
npm run tui
```

---

## 🔧 Konfiguration (Umgebungsvariablen)

Das Tool lässt sich flexibel über Umgebungsvariablen anpassen. Du kannst diese in deiner Shell setzen, bevor du das Tool startest:

### 1. CurseForge API-Key (`CURSEFORGE_API_KEY`)
Ohne diesen API-Key können keine automatischen CurseForge-Fingerprints abgeglichen werden. Unbekannte Mods werden dann im TUI angezeigt und können per manuellem Klick (mit integriertem Suchlink) zugeordnet werden.
```powershell
# Windows (PowerShell)
$env:CURSEFORGE_API_KEY="dein-api-key"
```

### 2. Parallelisierungs-Worker (`MC_SERVER_PACK_SCAN_WORKERS`)
Bestimmt, wie viele Mod-Dateien parallel analysiert und geastht werden sollen. Standardwert ist `8`.
```powershell
# Windows (PowerShell)
$env:MC_SERVER_PACK_SCAN_WORKERS="12"
```

---

## 🛠️ Funktionsweise im Detail (Workflow)

1. **Pfadauswahl**: Beim Start scannt das Tool deine lokalen Pfade auf Modrinth-Profile und listet diese auf. Du wählst den gewünschten Mods-Ordner und den Ausgabe-Pfad.
2. **Mod-Analyse (Scanner)**:
   - Die JAR-Dateien werden parallel eingelesen.
   - Der SHA-1-Hash für Modrinth und der MurmurHash2-Fingerprint für CurseForge werden berechnet.
   - Lokale Metadaten (wie `mods.toml` oder `fabric.mod.json`) werden extrahiert.
3. **API-Abgleich**:
   - Modrinth wird in schnellen Batches abgefragt. Wird eine Mod exakt gematcht, übernimmt das Tool die offizielle `client_side` / `server_side` Angabe.
   - Verbleibende Mods werden über die CurseForge-API (falls Key vorhanden) abgefragt.
4. **Entscheidungs-Phase (React TUI)**:
   - Eindeutige Server-Mods werden direkt grün markiert.
   - Eindeutige Client-Mods werden übersprungen.
   - Für alle CurseForge- oder unbekannten Mods öffnet sich ein interaktives Menü. Du siehst Details zur Mod und einen Direktlink zur Websuche. Mit der Tastatur entscheidest du: **s = Server**, **c = Client**, **k = Skip**, **o = Link öffnen**.
5. **Packen (Packer)**:
   - Alle als `server` markierten Mods werden in den Ausgabeordner kopiert.
   - Wichtige Server-Konfigurationsordner (z. B. `config`, `defaultconfigs`, `kubejs`, `datapacks`) werden aus deiner Instanz kopiert.
   - Startskripte (`start-server.ps1`/`.sh`) und ein JSON-Report mit allen Entscheidungen werden generiert.

---

## 📁 Projektstruktur

```text
Keksgames-Server-Modpack-Creator/
│
├── Keksgames-Server-Modpack-Creator/
│   ├── __init__.py
│   ├── __main__.py          # Einstiegspunkt für den CLI-Aufruf
│   ├── react_backend.py     # JSON-Backend für die React/Ink TUI
│   ├── tui.py               # Alte Textual TUI, nicht mehr der Standard-Einstieg
│   ├── scanner.py           # Parallelisierter JAR-Scanner & API-Verbindung
│   ├── packer.py            # Kopier- und Packlogik, Manifest- & Skript-Erstellung
│   ├── providers.py         # API-Clients für Modrinth & CurseForge
│   ├── models.py            # Datenklassen (ModCandidate, JarMetadata)
│   ├── discovery.py         # Autodetekt von Modrinth-Profilen
│   ├── jar_meta.py          # ZIP-Parser für fabric.mod.json, mods.toml etc.
│   └── hashes.py            # SHA-1 und MurmurHash2 Berechnungen
│
├── src/
│   └── cli.js               # React/Ink TUI
├── package.json             # Node-Abhängigkeiten & npm-Skripte
├── pyproject.toml           # Python Build-Definition
├── .gitignore               # Git Ausschlussmuster
└── README.md                # Dieses Dokument
```

---

## 📜 Lizenz

Dieses Projekt ist unter der **MIT-Lizenz** lizenziert. Siehe die Datei `LICENSE` für Details (oder nutze es frei nach den Richtlinien der MIT-Lizenz).

Erstellt mit ❤️ für die Minecraft Community.
