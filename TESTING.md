# Praxistest mit Discord

Die automatischen Tests (`tests/run_all.py`) arbeiten mit Testtönen und Rauschen und
messen Pegel. Ob es in Discord mit echter Sprache gut klingt, kann nur ein Mensch prüfen.
Diese Checkliste dauert etwa 15 Minuten. Am besten mit einer zweiten Person im
Sprachkanal oder mit Discords **Mikrofontest** (Einstellungen → Sprache & Video →
„Let's Check“).

Vorbereitung: Router läuft, ein virtuelles Mikro „Discord Mix“ ist angelegt.
In Discord: Einstellungen → Sprache & Video → **Eingabegerät: Discord Mix**.
Zum Vergleich hilft es, Discords eigene Rauschunterdrückung (Krisp) und
„Echo-Unterdrückung“ testweise **auszuschalten**.

## 1. Grundfunktion
- [ ] „Discord Mix“ erscheint in Discord als Eingabegerät
- [ ] Mikro → Discord Mix verbinden: Der Pegelbalken in Discord bewegt sich beim Sprechen
- [ ] Gegenüber hört dich klar, ohne Knacken, Aussetzer oder Roboterstimme
- [ ] Wire trennen: Gegenüber hört dich nicht mehr

## 2. Rauschunterdrückung
- [ ] Mikro → Rauschunterdrückung → Discord Mix
- [ ] Tastatur tippen / Lüfter ohne zu sprechen: kommt nicht (kaum) an
- [ ] Sprache klingt natürlich, Wortanfänge und -enden werden nicht abgeschnitten
      (sonst „Schwelle“ senken oder „Nachlauf“ erhöhen)

## 3. Kompressor
- [ ] Rauschunterdrückung → Kompressor → Discord Mix (Kette)
- [ ] Leise und laut sprechen/lachen: Lautstärke beim Gegenüber gleichmäßiger, kein Übersteuern

## 4. Musik mitschicken + Ducking
- [ ] Video/Musik in Firefox starten; Firefox → Ducking (**Musik**) → Discord Mix
- [ ] Mikro → Ducking (**Priorität**) **und** Mikro (bzw. Rauschunterdrückung) → Discord Mix
- [ ] Gegenüber hört die Musik; sobald du sprichst, wird sie deutlich leiser
- [ ] Nach dem Sprechen kommt die Musik sanft zurück (sonst „Rückkehr“ anpassen)
- [ ] Du selbst hörst die Musik weiterhin normal über deine Lautsprecher/Kopfhörer

## 5. Alltag
- [ ] Video pausieren und weiterspielen: Musik kommt wieder im Discord an
- [ ] Firefox schließen und neu öffnen: Route wird automatisch wiederhergestellt
- [ ] Router-Fenster schließen (Tray): Alles läuft weiter
- [ ] Ein/Aus-Schalter: Aus → Gegenüber hört nichts mehr vom Mix; An → alles wieder da
- [ ] Rechner neu starten (mit Autostart): Discord findet „Discord Mix“ wieder, Routen aktiv

## 6. Latenz
- [ ] Gegenüber empfindet keine merkliche Verzögerung (grob: < 100 ms zusätzlich).
      Jeder Effekt-Baustein addiert etwas Latenz; RNNoise am meisten (ca. 10 ms).

Bitte Probleme mit kurzer Beschreibung festhalten (was verbunden war, was zu hören war) –
am besten als Issue im Repository.
