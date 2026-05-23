# Minecraft Server Pack Creator

Ein simples TUI-Tool, das einen `mods`-Ordner aus einem Launcher-Profil scannt und daraus ein serverseitiges Modpack baut.

## Start

```powershell
python -m pip install -e .
mc-server-pack
```

Alternativ ohne Installation:

```powershell
python -m mc_server_pack_creator
```

## Was es macht

- findet typische Modrinth-App-Profile automatisch
- liest lokale `.jar`-Metadaten aus
- matcht Mods per SHA-1 auf Modrinth
- übernimmt Modrinths `client_side` / `server_side`-Angaben automatisch
- kann CurseForge-Dateien per Fingerprint matchen, wenn `CURSEFORGE_API_KEY` gesetzt ist
- zeigt CurseForge/unklare Mods einzeln mit Link und Server/Client-Buttons
- kopiert servergeeignete Mods plus typische Server-Konfigordner in einen fertigen Ausgabeordner
- schreibt einen Report mit allen Entscheidungen

## CurseForge API-Key

CurseForge-Fingerprints funktionieren nur mit API-Key:

```powershell
$env:CURSEFORGE_API_KEY="dein-key"
mc-server-pack
```

Ohne Key werden nicht auf Modrinth gefundene Mods trotzdem im TUI angezeigt, aber nur mit einem Suchlink. Du entscheidest dann per Button, ob sie auf den Server gehören.

## Scan-Geschwindigkeit

Der Scanner liest mehrere Mods parallel. Standard ist `8` Worker. Wenn du das anpassen willst:

```powershell
$env:MC_SERVER_PACK_SCAN_WORKERS="12"
mc-server-pack
```
