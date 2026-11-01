#!/bin/bash
# Uninstaller for Eglantine, installed by eglantine.sh.
# Removes the emulator and its generator (or batocera-launch emulator on
# Batocera 44+), the Switch 2 system and its settings from EmulationStation,
# the "Eglantine (emulator)" list entry, the F1 > Applications entry, the
# switch2 settings the installer added to batocera.conf, and the log.
# Games in /userdata/roms/switch2 and the emulator's own settings, keys and
# saves (/userdata/system/.config/eden, /userdata/system/.local/share/eden)
# are kept; settings changed from ES get back the emulator's own values.
# The BUA Python hook is shared with other add-ons, so it stays.

APP_NAME="Eglantine"

install_dir="/userdata/system/add-ons/eglantine"
es_config_dir="/userdata/system/configs/emulationstation"
rom_dir="/userdata/roms/switch2"
batocera_conf="/userdata/system/batocera.conf"
log_file="/userdata/system/logs/eglantine.log"
restore_script="/userdata/system/configs/eglantine/restore_desktop_entry.sh"

echo "Removing ${APP_NAME}..."

# The AppImage runs the emulator as a separate "eglantine" process, which
# can hang after a crash and ignore a normal stop
pkill -f "${install_dir}/eglantine.AppImage" >/dev/null 2>&1
pkill -x eglantine >/dev/null 2>&1
sleep 2
pkill -9 -x eglantine >/dev/null 2>&1

# Give the emulator back its own values for settings chosen in ES
[ -f "${install_dir}/eglantine-settings.py" ] && python3 "${install_dir}/eglantine-settings.py" >/dev/null 2>&1

rm -rf "${install_dir:?}"
rm -f "${es_config_dir}/es_systems_switch2.cfg" "${es_config_dir}/es_features_switch2.cfg" "${log_file}"

# Batocera 44+: the batocera-launch emulator, under any Python version's folder
rm -rf /userdata/system/.local/lib/python3*/site-packages/batocera_launch_eglantine \
       /userdata/system/.local/lib/python3*/site-packages/batocera_launch_eglantine-*.dist-info

# The "Eglantine (emulator)" entry in the Switch 2 list
rm -f "${rom_dir}/Eglantine.sw2" "${rom_dir}/images/eglantine.png"
if [ -f "${rom_dir}/gamelist.xml" ]; then
    xmlstarlet ed -d "/gameList/game[path='./Eglantine.sw2']" "${rom_dir}/gamelist.xml" > "${rom_dir}/gamelist.xml.tmp" \
        && mv "${rom_dir}/gamelist.xml.tmp" "${rom_dir}/gamelist.xml"
fi

# F1 > Applications entry and its restore at boot
rm -f /usr/share/applications/Eglantine.desktop
if [ -f /userdata/system/custom.sh ]; then
    sed -i "\|${restore_script}|d" /userdata/system/custom.sh
fi
rm -rf /userdata/system/configs/eglantine

if [ -f "${batocera_conf}" ]; then
    sed -i '/^switch2\.emulator=eglantine$/d; /^switch2\.core=eglantine$/d; /^switch2\.bezel=none$/d' "${batocera_conf}"
fi

echo "${APP_NAME} has been removed. Games in /userdata/roms/switch2 and the emulator's settings were kept."

killall -9 emulationstation
