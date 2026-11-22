# DIY Audio Router (Node-Editor)

Start (nutzt die vorhandene venv mit PySide6):

    cd ~/DIY_Audio_Router/node_router
    ../.venv/bin/python main.py

Voraussetzung: PipeWire + pipewire-pulse (`pw-dump`, `pw-link`, `pactl`).

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
