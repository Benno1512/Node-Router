# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/).

## [0.1.2] – 2026-11-23

### Neu
- **Effekt-Plugins mitgeliefert** (in `plugins/` und im AppImage): RNNoise (Rauschunterdrückung)
  und LSP (Kompressor, Ducking) – keine Zusatzinstallation mehr nötig; inkl. `libatomic`
  als Rückfall für Systeme ohne diese Bibliothek. Lizenzen und Herkunft: `plugins/README.md`
- **`install-deps.sh`**: installiert fehlende Systempakete (PipeWire, pipewire-pulse,
  WirePlumber, pactl) für Ubuntu/Debian/Mint, Fedora, Arch/Manjaro, openSUSE
- **Startprüfung**: fehlt etwas, zeigt die App beim Start den passenden Befehl
  (mit „Befehl kopieren“)

### Geändert
- `install.sh --with-rnnoise` ist nicht mehr nötig (Option wird ignoriert)

## [0.1.1] – 2026-11-23

### Neu
- **AppImage**: eine einzelne startbare Datei (`DIY-Audio-Router-0.1.1-x86_64.AppImage`)
  mit Python, PySide6 und Qt – herunterladen, ausführbar machen, starten
- `build_appimage.sh` zum Selbstbauen, `tests/test_appimage.py`

### Geändert
- Als AppImage liegen Config und Effekt-Dateien in `~/.config/diy-audio-router/` bzw.
  `~/.local/share/diy-audio-router/` (aus dem Quellcode gestartet: unverändert neben dem Programm)
- System-Programme (pw-link, pactl, pipewire …) werden aus dem AppImage mit der
  System-Umgebung gestartet, nicht mit den Bibliotheken des Bundles
- Autostart-/Startmenü-Einträge zeigen beim AppImage auf die AppImage-Datei

## [0.1.0] – 2026-11-22

Erste Version.

### Routing
- Zwei feste Listen: Quellen (Eingabegeräte, App-Streams) links, Ziele (Ausgabegeräte,
  virtuelle Mikrofone) rechts; Verbindungen per Drag & Drop als direkte `pw-link`-Links
- Routen, Reihenfolge und Einstellungen in `config.json`; Routen werden wiederhergestellt,
  wenn eine App neu startet oder pausiert und weiterspielt
- Pausierte Apps bleiben als ausgegraute Karte stehen, gespeicherte Routen gestrichelt
- Getrennte WirePlumber-Verbindungen bleiben getrennt (blockierte Routen)
- Ignorieren-Liste für Apps/Geräte, die nie angezeigt werden sollen (z. B. Systemklänge)
- Virtuelle Mikrofone (`Audio/Source/Virtual`) für Discord & Co.
- Lautstärke und Stumm pro Gerät/App (0–150 %)

### Effekt-Bausteine (PipeWire filter-chain)
- Hochpass, Equalizer (3 Bänder), Delay, Hall
- Rauschunterdrückung (RNNoise), Kompressor, Ducking mit Musik- und Prioritätseingang
  (LSP-Plugins)
- Frei im Netz verschiebbar, Regler wirken live, laufen weiter, wenn der Router geschlossen ist

### Bedienung und Betrieb
- Ein/Aus-Schalter: trennt alle eigenen Verbindungen und stoppt Effekte, Programm bleibt offen
- Design Dunkel/Hell/Wie System
- Tray-Symbol, Hintergrundbetrieb, Autostart (minimiert), nur eine Instanz
- Erkennt Neustarts von PipeWire und stellt virtuelle Mikros, Effekte und Routen wieder her
- `install.sh` (venv, Startmenü-Eintrag, optional Autostart und RNNoise-Download)
- Automatische Tests (`tests/run_all.py`) und manueller PipeWire-Neustart-Test

### Bekannte Grenzen
- Nur getestet mit Ubuntu 24.04, PipeWire 1.0.5, WirePlumber 0.4.17
- Noch nicht mit Discord und echter Sprache getestet (siehe `TESTING.md`)

[0.1.2]: https://github.com/benborofn-lgtm/Audio-Router/releases/tag/v0.1.2
[0.1.1]: https://github.com/benborofn-lgtm/Audio-Router/releases/tag/v0.1.1
[0.1.0]: https://github.com/benborofn-lgtm/Audio-Router/releases/tag/v0.1.0
