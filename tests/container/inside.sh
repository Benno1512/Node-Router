#!/usr/bin/env bash
# Runs inside the test container: starts a private PipeWire session with virtual
# devices (no hardware), then the test suite. Arguments are passed to run_all.py.
set -uo pipefail

export XDG_RUNTIME_DIR=/tmp/xdg QT_QPA_PLATFORM=offscreen
mkdir -p -m 700 "$XDG_RUNTIME_DIR"
dbus-daemon --session --address="unix:path=$XDG_RUNTIME_DIR/bus" --fork --nopidfile >/dev/null
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"

pipewire >/tmp/pipewire.log 2>&1 &
sleep 1
wireplumber >/tmp/wireplumber.log 2>&1 &
pipewire-pulse >/tmp/pipewire-pulse.log 2>&1 &
for _ in $(seq 50); do pactl info >/dev/null 2>&1 && break; sleep 0.2; done

# virtual "hardware": a speaker and a microphone
pactl load-module module-null-sink sink_name=test_speakers \
    'sink_properties="device.description=\"Test Speakers\""' >/dev/null
# (a null sink declared as Audio/Source fails to start in PipeWire 1.6, so the
#  microphone is a remap of the speakers' monitor: a real Audio/Source)
pactl load-module module-remap-source master=test_speakers.monitor source_name=test_mic \
    'source_properties="device.description=\"Test Microphone\""' >/dev/null
pactl set-default-sink test_speakers
sleep 1

echo "== $(. /etc/os-release; echo "$PRETTY_NAME")"
pipewire --version | sed -n 2p
wireplumber --version | sed -n 2p
/venv/bin/python -c 'import PySide6, sys; print("Python", sys.version.split()[0], "· PySide6", PySide6.__version__)'
wpctl status | sed -n '/Audio/,/Video/p' | head -30
echo

cd /src
/venv/bin/python tests/run_all.py "$@"
code=$?
if [ "$code" != 0 ]; then
    echo; echo "== processes"; ps -eo pid,stat,comm | grep -E "pipewire|wireplumber" || true
    for f in pipewire pipewire-pulse wireplumber; do
        echo "== $f log (last 15 lines, without rtkit noise)"
        grep -v -e rtkit -e mod.rt "/tmp/$f.log" | tail -15
    done
fi
exit $code
