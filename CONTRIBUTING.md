# Contributing

Thanks for wanting to help! Bug reports, test reports from other setups and pull requests are all
welcome.

Questions, ideas and setups you want to share go to
[Discussions](https://github.com/benborofn-lgtm/Node-Router/discussions).

## Reporting a problem

Please open an [issue](https://github.com/benborofn-lgtm/Node-Router/issues) and include:

- your distribution and version, plus the output of `pipewire --version` and `wireplumber --version`
- whether you use the AppImage or run from source
- what was connected and what you expected or heard instead
- the terminal output, if you started Node-Router from a terminal

**Testing on other systems helps a lot.** Node-Router is only tested on Ubuntu 24.04 with
PipeWire 1.0.5 and WirePlumber 0.4.17. A run through the checklist in [TESTING.md](TESTING.md)
on another distribution or with WirePlumber 0.5 is very useful, even if everything works.

## Development setup

    git clone https://github.com/benborofn-lgtm/Node-Router.git
    cd Node-Router
    ./install.sh
    .venv/bin/python main.py

The code is plain Python with PySide6, with no build step:

| File | Contents |
|---|---|
| `main.py` | window, cards, wires, routing logic, tray |
| `pw_backend.py` | reading the PipeWire graph (`pw-dump`), links, volumes, virtual mics |
| `fx.py` | effect blocks: filter-chain configs, processes |
| `levels.py` | level meters |
| `deps.py`, `paths.py` | system check, file locations (source vs. AppImage) |

## Tests

    .venv/bin/python tests/run_all.py            # all (about 10 minutes)
    .venv/bin/python tests/run_all.py fx ghost   # only tests whose name contains these

- **Close Node-Router first.** Otherwise the runner aborts.
- The tests open real windows and create real PipeWire objects (named `diy_selftest_*`). They use
  their own config in a temp folder, play nothing through your speakers and clean up afterwards.
- Please add or extend a test for new behavior, and run the whole suite before opening a pull
  request.

## Pull requests

- Keep each pull request to one topic and describe what you checked.
- User-facing text is in English.
- New features go under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
- By contributing you agree that your code is licensed under GPL-3.0-or-later, like the rest of
  the project.
