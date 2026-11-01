#!/bin/bash
# Uninstaller for Eglantine, installed by eglantine.sh.
# Removes the emulator and its generator (or batocera-launch emulator on
# Batocera 44+), the Switch 2 system from EmulationStation, the switch2
# settings the installer added to batocera.conf, and the log.
# Games in /userdata/roms/switch2 and the emulator's own settings, keys and
# saves (/userdata/system/.config/eden, /userdata/system/.local/share/eden)
# are kept. The BUA Python hook is shared with other add-ons, so it stays.

APP_NAME="Eglantine"

install_dir="/userdata/system/add-ons/eglantine"
es_systems="/userdata/system/configs/emulationstation/es_systems_switch2.cfg"
batocera_conf="/userdata/system/batocera.conf"
log_file="/userdata/system/logs/eglantine.log"

echo "Removing ${APP_NAME}..."

# The AppImage runs the emulator as a separate "eglantine" process, which
# can hang after a crash and ignore a normal stop
pkill -f "${install_dir}/eglantine.AppImage" >/dev/null 2>&1
pkill -x eglantine >/dev/null 2>&1
sleep 2
pkill -9 -x eglantine >/dev/null 2>&1

rm -rf "${install_dir:?}"
rm -f "${es_systems}" "${log_file}"

# Batocera 44+: the batocera-launch emulator, under any Python version's folder
rm -rf /userdata/system/.local/lib/python3*/site-packages/batocera_launch_eglantine \
       /userdata/system/.local/lib/python3*/site-packages/batocera_launch_eglantine-*.dist-info

if [ -f "${batocera_conf}" ]; then
    sed -i '/^switch2\.emulator=eglantine$/d; /^switch2\.core=eglantine$/d; /^switch2\.bezel=none$/d' "${batocera_conf}"
fi

echo "${APP_NAME} has been removed. Games in /userdata/roms/switch2 and the emulator's settings were kept."

killall -9 emulationstation
