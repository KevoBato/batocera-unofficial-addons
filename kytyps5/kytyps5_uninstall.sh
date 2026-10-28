#!/bin/bash
# Uninstaller for KytyPS5, installed by kytyps5.sh.
# Removes the emulator and its generator, the PS5 system from EmulationStation,
# the ps5 settings the installer added to batocera.conf, and the log.
# Games in /userdata/roms/ps5 are kept. The BUA Python hook is shared with
# other add-ons, so it stays.

APP_NAME="KytyPS5"

install_dir="/userdata/system/add-ons/kytyps5"
es_systems="/userdata/system/configs/emulationstation/es_systems_ps5.cfg"
batocera_conf="/userdata/system/batocera.conf"
log_file="/userdata/system/logs/kyty.log"

echo "Removing ${APP_NAME}..."

pkill -f "${install_dir}/kyty_emulator" >/dev/null 2>&1

rm -rf "${install_dir:?}"
rm -f "${es_systems}" "${log_file}"

if [ -f "${batocera_conf}" ]; then
    sed -i '/^ps5\.emulator=kyty$/d; /^ps5\.core=kyty$/d; /^ps5\.bezel=none$/d' "${batocera_conf}"
fi

echo "${APP_NAME} has been removed. Games in /userdata/roms/ps5 were kept."

killall -9 emulationstation
