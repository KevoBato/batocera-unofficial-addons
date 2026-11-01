#!/bin/bash
# Launch wrapper for Eglantine (Switch 2), called by the eglantine generator
# (or batocera-launch emulator on Batocera 44+) with the game's .sw2 folder.

install_dir="/userdata/system/add-ons/eglantine"
log_file="/userdata/system/logs/eglantine.log"
qt_config="/userdata/system/.config/eden/qt-config.ini"

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

# Auto-detect the X display (it can be :0 or :1 depending on how X started)
[ -n "$DISPLAY" ] || export DISPLAY=:$(ls /tmp/.X11-unix | head -n1 | tr -dc 0-9).0
export QT_QPA_PLATFORM=xcb
unset WAYLAND_DISPLAY

# A Switch 2 dump is a folder (base/exefs/main, base/romfs, ...); the
# emulator wants its exefs/main file
target="${@: -1}"
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

# exec keeps the emulator in the foreground so the launcher waits for it
exec "$install_dir/eglantine.AppImage" -f -g "$game" > "$log_file" 2>&1
