#!/bin/bash
# Launch wrapper for Eglantine (Switch 2), called by the eglantine generator
# (or batocera-launch emulator on Batocera 44+) with the game's .sw2 folder.
# With no game, or with the "Eglantine.sw2" entry the installer puts in the
# Switch 2 list (a file, not a folder), it opens the emulator's own window,
# for keys, firmware, controllers and settings. F1 > Applications uses that too.

install_dir="/userdata/system/add-ons/eglantine"
log_file="/userdata/system/logs/eglantine.log"
qt_config="/userdata/system/.config/eden/qt-config.ini"

# Auto-detect the X display (it can be :0 or :1 depending on how X started)
[ -n "$DISPLAY" ] || export DISPLAY=:$(ls /tmp/.X11-unix | head -n1 | tr -dc 0-9).0
export QT_QPA_PLATFORM=xcb
unset WAYLAND_DISPLAY

# Hotkey+Start sends Alt+F4, which the emulator answers with "Are you sure
# you want to close?" unless it is told never to ask (confirmStop: 0 always
# ask, 1 depends on the game, 2 never ask)
if [ ! -f "$qt_config" ]; then
    mkdir -p "$(dirname "$qt_config")"
    printf '[UI]\nconfirmStop\\default=false\nconfirmStop=2\n' > "$qt_config"
elif grep -q '^confirmStop=' "$qt_config"; then
    sed -i 's/^confirmStop\\default=.*/confirmStop\\default=false/; s/^confirmStop=.*/confirmStop=2/' "$qt_config"
elif grep -q '^\[UI\]$' "$qt_config"; then
    sed -i 's/^\[UI\]$/[UI]\nconfirmStop\\default=false\nconfirmStop=2/' "$qt_config"
fi

# The last argument is the game; with no arguments ${@: -1} would be $0
target=""
[ $# -gt 0 ] && target="${@: -1}"

# The emulator's window: put back its own settings (no game's ES choices)
if [ -z "$target" ] || { [ -f "$target" ] && [ "${target##*.}" = "sw2" ]; }; then
    python3 "$install_dir/eglantine-settings.py" > "$log_file" 2>&1
    exec "$install_dir/eglantine.AppImage" >> "$log_file" 2>&1
fi

# A Switch 2 dump is a folder (base/exefs/main, base/romfs, ...); the
# emulator wants its exefs/main file
game="$target"
if [ -d "$target" ]; then
    game=""
    for candidate in base/exefs/main exefs/main; do
        if [ -f "$target/$candidate" ]; then
            game="$target/$candidate"
            break
        fi
    done
    [ -n "$game" ] || game=$(find "$target" -maxdepth 4 -type f -path "*/exefs/main" | sort | head -n1)
fi
if [ ! -f "$game" ]; then
    echo "No exefs/main found in $target" > "$log_file"
    exit 1
fi

# The settings chosen for this game (or the system) in EmulationStation
python3 "$install_dir/eglantine-settings.py" "$target" > "$log_file" 2>&1

# Some games make the emulator use up all the RAM, which freezes the whole
# machine (no keyboard, no SSH) long before Linux steps in. Start it marked as
# the first thing to kill when memory runs out, and watch the free memory:
# below the limit, the emulator is killed and ES comes back.
# Loading can take over 2 GB a second, so it checks 4 times a second.
# EGLANTINE_MIN_FREE_MB=<MB> sets the limit (default 10% of RAM, at least 1.5 GB).
# setsid gives the AppImage and the emulator it starts their own process
# group, so the watchdog can kill them all whatever the emulator is called.
(echo 1000 > /proc/self/oom_score_adj; exec setsid "$install_dir/eglantine.AppImage" -f -g "$game") >> "$log_file" 2>&1 &
pid=$!
renice -n -10 $$ >/dev/null 2>&1

total_mb=0
while read -r name value unit; do
    [ "$name" = "MemTotal:" ] && total_mb=$((value / 1024)) && break
done < /proc/meminfo
min_free_mb=${EGLANTINE_MIN_FREE_MB:-$((total_mb / 10))}
[ -n "$EGLANTINE_MIN_FREE_MB" ] || [ "$min_free_mb" -ge 1536 ] || min_free_mb=1536
echo "[eglantine] memory watchdog: ${total_mb} MB RAM, kills the emulator below ${min_free_mb} MB free" >> "$log_file"

while kill -0 "$pid" 2>/dev/null; do
    available_mb=""
    while read -r name value unit; do
        [ "$name" = "MemAvailable:" ] && available_mb=$((value / 1024)) && break
    done < /proc/meminfo
    if [ -n "$available_mb" ] && [ "$available_mb" -lt "$min_free_mb" ]; then
        echo "[eglantine] only ${available_mb} MB of memory left, closing the emulator before the machine freezes" >> "$log_file"
        kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        break
    fi
    sleep 0.25
done
wait "$pid"
