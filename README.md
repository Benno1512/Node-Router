# Node-Router

PipeWire-Patchbay im Node-RED-Stil: Quellen links, Ziele rechts, dazwischen Verbindungen
und Effekt-Bausteine. Virtuelle Mikrofone z. B. für Discord.

## Als einzelne Datei (AppImage)

Unter [Releases](https://github.com/benborofn-lgtm/Audio-Router/releases) die Datei
`Node-Router-<version>-x86_64.AppImage` herunterladen, dann:

    chmod +x Node-Router-*-x86_64.AppImage     # oder: Rechtsklick → Eigenschaften → Ausführbar
    ./Node-Router-*-x86_64.AppImage

Keine Installation, kein Python nötig – Qt und alle Effekt-Plugins (Rauschunterdrückung,
Kompressor, Ducking) sind enthalten. Einstellungen liegen in `~/.config/node-router/`,
Effekt-Dateien in `~/.local/share/node-router/`.
Selbst bauen: `./build_appimage.sh` (lädt PySide6, PyInstaller und appimagetool).

## Was du brauchst

Vom System kommt nur der **Sound-Server**: PipeWire mit pipewire-pulse und WirePlumber
plus deren Kommandozeilen-Werkzeuge (`pw-link`, `pactl` …). Auf aktuellen Desktop-Systemen
ist das vorinstalliert (Ubuntu ab 22.10, Fedora ab 34, Linux Mint 22, Manjaro/Arch mit
KDE/GNOME). Fehlt etwas, sagt die App beim Start Bescheid und zeigt den Befehl. Oder:

    ./install-deps.sh          # erkennt die Distribution, fragt vor dem Installieren

Das Skript führt je nach System aus (danach einmal ab- und wieder anmelden):

| System | Befehl |
|---|---|
| Ubuntu, Debian, Mint | `sudo apt install pipewire pipewire-pulse pipewire-bin wireplumber pulseaudio-utils libsndfile1 libxcb-cursor0` |
| Fedora | `sudo dnf install pipewire pipewire-pulseaudio pipewire-utils wireplumber pulseaudio-utils libsndfile xcb-util-cursor` |
| Arch, Manjaro | `sudo pacman -S --needed pipewire pipewire-pulse wireplumber libpulse libsndfile xcb-util-cursor` |
| openSUSE | `sudo zypper install pipewire pipewire-pulseaudio pipewire-tools wireplumber pulseaudio-utils libsndfile1 libxcb-cursor0` |
| alle | `systemctl --user enable --now pipewire pipewire-pulse wireplumber` |

Getestet ist nur Ubuntu 24.04; die übrigen Paketnamen stammen aus den offiziellen
Paketquellen. Das AppImage braucht außerdem glibc ≥ 2.39 (Ubuntu 24.04, Fedora 40 und neuer).

## Installation aus dem Quellcode

Voraussetzung: Linux mit **PipeWire + pipewire-pulse** und WirePlumber, Python ≥ 3.10.
Getestet mit Ubuntu 24.04 (PipeWire 1.0.5, WirePlumber 0.4.17).

    git clone https://github.com/benborofn-lgtm/Audio-Router.git
    cd Audio-Router
    ./install.sh                         # optional: --autostart

`install.sh` prüft die Systempakete, legt `.venv` an, installiert PySide6 und erstellt einen
Startmenü-Eintrag „Node-Router“. Kein root nötig. Optional:

- Die Effekt-Plugins liegen bereits in `plugins/` (siehe `plugins/README.md`)
- `./install.sh --uninstall` entfernt Startmenü- und Autostart-Eintrag

Manuell starten: `.venv/bin/python main.py` (bzw. `--minimized`: nur ins Tray).

## Hintergrundbetrieb

Fenster schließen = Router läuft im **Tray** weiter (Symbol in der Taskleiste: Öffnen,
Aktiv/Deaktiviert, Beenden). Nur solange er läuft, werden Routen bei App-Neustarts
wiederhergestellt, blockierte Routen durchgesetzt und virtuelle Mikros/Effekte nach einem
Neustart von PipeWire neu angelegt. **⋯ → Beim Anmelden starten** startet ihn automatisch
(minimiert). Ein zweiter Start öffnet nur das vorhandene Fenster.

## Bedienung

- Links: Eingabegeräte (grün) und Anwendungs-Streams (blau)
- Rechts: echte Ausgabegeräte (orange) und virtuelle Mikrofone (lila)
- Port ziehen → Port: verbinden · Wire anklicken + Entf / Doppelklick: trennen
- Zwei feste Listen an der linken und rechten Fensterkante, dazwischen die Routing-Fläche.
  Einträge nur hoch/runter ziehen (Sortierung wird gespeichert). Kein Zoom, kein seitliches Scrollen.
- Rechtsklick: virtuelles Mikro anlegen/umbenennen/löschen
- Jede Karte hat einen Lautstärkeregler (0–150 %, Strich = 100 %): ziehen, Mausrad ±5 %,
  Doppelklick = 100 %, Lautsprecher-Symbol = stumm. Wirkt auf das ganze Gerät bzw. die
  ganze App (wie pavucontrol), nicht auf einzelne Verbindungen.
- **● Aktiv / ○ Deaktiviert** (oben): schaltet den Router aus, ohne ihn zu schließen – eigene
  Verbindungen werden getrennt, Effekte gestoppt, gesperrte App→Standard-Lautsprecher-Verbindungen
  wiederhergestellt; virtuelle Mikros bleiben. Erneut klicken stellt alles wieder her.
- ⋯ → Design: Dunkel, Hell oder „Wie System“ (folgt dem KDE/GNOME-Farbschema live)
- In Discord: Einstellungen → Sprache & Video → Eingabegerät → dein virtuelles Mikro

## Effekt-Bausteine

Doppelklick in die Routing-Fläche (oder Rechtsklick → Baustein hinzufügen) öffnet das
Baustein-Menü: **Hochpass**, **Equalizer** (Bass/Mitten/Höhen), **Delay**, **Hall**,
**Rauschunterdrückung** (RNNoise), **Kompressor** und **Ducking**.

- **Ducking** hat zwei Eingänge: *Musik* wird abgesenkt, sobald *Priorität* (z. B. dein Mikro)
  die Schwelle überschreitet. Der Ausgang liefert die abgesenkte Musik – die Priorität selbst
  zusätzlich direkt mit dem Ziel verbinden (ein Ausgang kann mehrere Wires haben).
- Benötigt: `sudo apt install lsp-plugins-ladspa` (Kompressor, Ducking) und
  `plugins/librnnoise_ladspa.so` aus github.com/werman/noise-suppression-for-voice (v1.10,
  braucht `libatomic1`). Fehlt etwas, ist der Eintrag im Menü ausgegraut, der Tooltip sagt warum.

Bausteine lassen sich frei im Netz verschieben und wie Ein-/Ausgänge verbinden
(Quelle → Baustein → Baustein → Ziel). Regler wirken live; Mausrad = fein,
Doppelklick = Standardwert. Rechtsklick auf einen Baustein: zurücksetzen, trennen, entfernen.

Technik: Jeder Baustein ist ein eigener `pipewire -c fx/<id>.conf`-Prozess (PipeWire
filter-chain, Nodes `diy_fx_<id>_in/_out`, ohne Autoconnect). Er läuft weiter, wenn
der Router geschlossen wird, und wird beim Start wiederverwendet bzw. neu gestartet.
Nur „Nachhall“ beim Hall erzeugt eine neue Impulsantwort und startet den Baustein kurz
neu (Verbindungen werden automatisch wiederhergestellt).

Gespeichert in `config.json` (virtuelle Mikros, Effekt-Bausteine, eigene Routen, blockierte Routen,
Reihenfolge der Listen). Routen werden automatisch wiederhergestellt, wenn eine App neu startet.

Verschwindet eine App oder ein Gerät (z. B. Video pausiert), bleibt die Karte ausgegraut an
ihrem Platz; gespeicherte Verbindungen werden gestrichelt angezeigt und beim Zurückkommen
wiederhergestellt. Auch an ausgegraute Karten kann man Verbindungen anlegen/trennen (nur die
gespeicherte Route). Rechtsklick → „Aus Liste entfernen“ entfernt die Karte (Routen bleiben).

Rechtsklick → „Ignorieren“ blendet eine App/ein Gerät dauerhaft aus – auch wenn es erneut Ton
abspielt (z. B. libcanberra/Systemklänge). Rückgängig: ⋯ → Ausgeblendet → wieder anzeigen.
Bestehende Verbindungen/Routen werden dabei nicht verändert.

Getrennte Verbindungen werden als „blockiert“ gemerkt: Legt WirePlumber z. B. beim
Neustart einer App den Link App → Lautsprecher wieder an, entfernt das Programm ihn
(nach ca. 0,2 s – so lange ist die App kurz zu hören). Erneutes Verbinden per Drag
hebt die Blockierung auf. Wirkt nur, solange das Programm läuft.

## Tests

    cd node_router
    ../.venv/bin/python tests/run_all.py            # alle (ca. 10 Minuten)
    ../.venv/bin/python tests/run_all.py fx ghost   # nur Tests, deren Name das enthält

- **Router vorher schließen** – der Runner bricht sonst ab. Ein offener Router würde sich alle
  Test-Objekte in seiner `config.json` merken.
- Die Tests öffnen echte Fenster (grafische Sitzung nötig) und legen echte PipeWire-Objekte an:
  virtuelle Test-Mikros `diy_selftest_*`, stumme Test-Streams, Effekt-Prozesse. Sie benutzen eine
  eigene Config im Temp-Ordner und spielen nichts über die Lautsprecher ab. Danach räumt der
  Runner Test-Reste auf – deine eigenen Effekt-Bausteine (aus `config.json`) fasst er nicht an.
- `test_fx_plugins` wird übersprungen, wenn LSP-Plugins oder RNNoise fehlen.
- `tests/test_pipewire_restart.py --ja-wirklich` startet PipeWire **echt** neu (kurze Ton-
  unterbrechung für alle Programme) und prüft, dass Mikro, Effekt, Routen und Ton zurückkommen.
  Nicht Teil von `run_all.py`; nur manuell ausführen.

| Test | prüft |
|---|---|
| `selftest.py` | Umgebung, Graph lesen, virtuelles Mikro, Verbinden/Trennen, GUI offscreen |
| `test_menu` | Baustein-Menü: Beschreibungen, gesperrte Einträge, Klick/Loslassen |
| `test_order` | feste Listen an den Fensterkanten, Sortieren, Größenänderung, kein Zoom |
| `test_volume` | Lautstärkeregler und Stumm-Knopf gegen `wpctl` |
| `test_theme` | Dunkel/Hell/System, Umschalten ohne Neustart |
| `test_ignore` | Ignorieren und wieder anzeigen |
| `test_ghost` | ausgegraute Karten, gestrichelte Routen, Wiederherstellung |
| `test_blocked` | blockierte Routen gegen WirePlumber-Neuverbindung |
| `test_power` | Ein/Aus-Knopf |
| `test_background` | Tray, Autostart-Schalter, Einzelinstanz, Neustart der Überwachung, verlorene virtuelle Mikros |
| `test_fx` | Hochpass/EQ/Delay/Hall: Signal, Regler, Verschieben, Neustart, Entfernen |
| `test_fx_plugins` | Rauschunterdrückung, Kompressor, Ducking mit zwei Eingängen |

## Bekannte Grenzen

- Getestet nur mit **Ubuntu 24.04, PipeWire 1.0.5, WirePlumber 0.4.17**. Neuere Versionen
  (insbesondere WirePlumber 0.5 mit anderer Konfiguration) sind ungetestet.
- Noch **nicht mit Discord und echter Sprache** getestet – Checkliste: [TESTING.md](TESTING.md).
- Routen wiederherstellen, blockierte Routen und das Neuanlegen von Mikros/Effekten nach einem
  PipeWire-Neustart funktionieren nur, solange der Router läuft (Tray/Autostart nutzen).
- Ist eine blockierte App neu gestartet, ist sie bis zu ca. 0,3 s über den Standard-Lautsprecher
  zu hören, bevor der Router die WirePlumber-Verbindung trennt.
- Lautstärke pro **Verbindung** gibt es noch nicht (nur pro Gerät/App).

## Lizenz

GPL-3.0-or-later, siehe [LICENSE](LICENSE). Änderungen: [CHANGELOG.md](CHANGELOG.md).
Mitgelieferte Plugins anderer Projekte ([LSP-Plugins](https://lsp-plug.in/), LGPL-3.0;
[RNNoise](https://github.com/werman/noise-suppression-for-voice), GPL-3.0; libatomic aus GCC)
stehen unter ihren eigenen Lizenzen – Details, Versionen und Quellen in `plugins/README.md`.
