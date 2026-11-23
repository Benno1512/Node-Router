# Bundled plugins (third party)

These LADSPA plugins ship unmodified (as x86_64 binaries) in the repository and in the AppImage,
so all effect blocks work without installing anything else. They are not part of Node-Router and
keep their own licenses.

| File | Project / version | License | Source |
|---|---|---|---|
| `librnnoise_ladspa.so` | noise-suppression-for-voice **v1.10** (RNNoise) – noise suppression | GPL-3.0 → `LICENSES/GPL-3.0.txt` | Binary from `linux-rnnoise.zip` of the release: https://github.com/werman/noise-suppression-for-voice/releases/tag/v1.10 · Source code: https://github.com/werman/noise-suppression-for-voice/tree/v1.10 |
| `lsp-plugins-ladspa.so` | LSP Plugins **1.2.14** (Debian/Ubuntu package `lsp-plugins-ladspa` 1.2.14-1) – compressor, ducking | LGPL-3.0-or-later → `LICENSES/LGPL-3.0.txt`, details in `LICENSES/lsp-plugins-debian-copyright.txt` | Ubuntu 24.04 (noble/universe) · Source code: https://github.com/lsp-plugins/lsp-plugins/releases/tag/1.2.14 or `apt source lsp-plugins` |
| `libatomic.so.1` | GCC runtime library libatomic (Ubuntu `libatomic1` 14.2.0-4ubuntu2~24.04.1). RNNoise needs it, and some systems lack it | GPL-3.0 with *GCC Runtime Library Exception* → `LICENSES/libatomic-gcc-copyright.txt` | Ubuntu 24.04 · Source code: https://gcc.gnu.org or `apt source gcc-14` |

SHA-256:

    ba2b420c76cd2f1e7684430c96fef8c533041d5f67b94060f8eeda6af1701f97  librnnoise_ladspa.so
    973316cf998d3e48797f2d8aeb151e74bfb227d17df739a53ef6b58f0e4f260f  lsp-plugins-ladspa.so
    9d8a34468e614a71a6427dbabb0ac24eb8cb1e324dc6aa3bf95eb6f59201f000  libatomic.so.1

Runtime dependencies that come from the system: `libsndfile` (always present, because PipeWire
uses it itself), `libstdc++` and `libc`.

The router looks for plugins in this order:
1. `~/.local/share/node-router/plugins` (AppImage only)
2. this folder
3. the system folders (`/usr/lib/ladspa` …)

So a newer version can simply be dropped into the user folder.
