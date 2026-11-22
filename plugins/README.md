# Mitgelieferte Plugins (Drittanbieter)

Damit alle Effekt-Bausteine ohne Zusatzinstallation funktionieren, liegen diese
LADSPA-Plugins unverändert (als Binärdateien, x86_64) im Repository und im AppImage.
Sie gehören nicht zum DIY Audio Router und stehen unter ihren eigenen Lizenzen.

| Datei | Projekt / Version | Lizenz | Quelle |
|---|---|---|---|
| `librnnoise_ladspa.so` | noise-suppression-for-voice **v1.10** (RNNoise) – Rauschunterdrückung | GPL-3.0 → `LICENSES/GPL-3.0.txt` | Binärdatei aus `linux-rnnoise.zip` des Releases: https://github.com/werman/noise-suppression-for-voice/releases/tag/v1.10 · Quellcode: https://github.com/werman/noise-suppression-for-voice/tree/v1.10 |
| `lsp-plugins-ladspa.so` | LSP Plugins **1.2.14** (Debian/Ubuntu-Paket `lsp-plugins-ladspa` 1.2.14-1) – Kompressor, Ducking | LGPL-3.0-or-later → `LICENSES/LGPL-3.0.txt`, Details `LICENSES/lsp-plugins-debian-copyright.txt` | Ubuntu 24.04 (noble/universe) · Quellcode: https://github.com/lsp-plugins/lsp-plugins/releases/tag/1.2.14 bzw. `apt source lsp-plugins` |
| `libatomic.so.1` | GCC-Laufzeitbibliothek libatomic (Ubuntu `libatomic1` 14.2.0-4ubuntu2~24.04.1) – wird von RNNoise benötigt und fehlt auf manchen Systemen | GPL-3.0 mit *GCC Runtime Library Exception* → `LICENSES/libatomic-gcc-copyright.txt` | Ubuntu 24.04 · Quellcode: https://gcc.gnu.org bzw. `apt source gcc-14` |

SHA-256:

    ba2b420c76cd2f1e7684430c96fef8c533041d5f67b94060f8eeda6af1701f97  librnnoise_ladspa.so
    973316cf998d3e48797f2d8aeb151e74bfb227d17df739a53ef6b58f0e4f260f  lsp-plugins-ladspa.so
    9d8a34468e614a71a6427dbabb0ac24eb8cb1e324dc6aa3bf95eb6f59201f000  libatomic.so.1

Laufzeit-Abhängigkeiten, die vom System kommen: `libsndfile` (immer vorhanden, weil
PipeWire sie selbst nutzt), `libstdc++`, `libc`.

Der Router sucht Plugins in dieser Reihenfolge: `~/.local/share/diy-audio-router/plugins`
(nur AppImage), dieser Ordner, dann die System-Ordner (`/usr/lib/ladspa` …). Eine neuere
Version lässt sich also einfach im Benutzerordner ablegen.
