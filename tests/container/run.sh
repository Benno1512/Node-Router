#!/usr/bin/env bash
# Runs the test suite against a current PipeWire/WirePlumber in a Fedora container
# (rootless podman, virtual devices only – your own sound system is not touched).
#
#   tests/container/run.sh              all tests
#   tests/container/run.sh fx ghost     only tests whose name contains these
#
# The container gets a copy of the repository (tracked files + local changes), so
# test files never end up in your working copy.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="node-router-test:fedora"
command -v podman >/dev/null || { echo "podman is missing (sudo apt install podman)"; exit 1; }

podman build -q -t "$IMAGE" -f "$DIR/tests/container/Containerfile" "$DIR" >/dev/null

SRC="$(mktemp -d "${TMPDIR:-/tmp}/node-router-src.XXXXXX")"
trap 'rm -rf "$SRC"' EXIT
(cd "$DIR" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf -) | tar -xf - -C "$SRC"

podman run --rm --network=none -v "$SRC:/src:Z" "$IMAGE" bash /src/tests/container/inside.sh "$@"
