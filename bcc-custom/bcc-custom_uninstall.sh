#!/bin/bash
# Uninstaller for Modern Control Center (bcc-custom.sh): Batocera's own
# Control Center comes back straight away. Your own files in
# /userdata/system/configs/controlcenter (and the Apps tab's apps.json) are kept.

APP_NAME="Modern Control Center"
install_dir="/userdata/system/add-ons/bcc-custom"
service_file="/userdata/system/services/bcc_custom"

echo "Removing ${APP_NAME}..."

if [ -f "$service_file" ]; then
    bash "$service_file" stop
    batocera-services disable bcc_custom >/dev/null 2>&1
    rm -f "$service_file"
fi

# Never delete while it is still laid over Batocera's Control Center
if awk '$2=="/usr/share/batocera/controlcenter" {f=1} END {exit !f}' /proc/mounts; then
    echo "The Control Center is still in use; restart Batocera and uninstall again."
    exit 1
fi
rm -rf "${install_dir:?}"
rm -f /userdata/system/.local/share/applications/bcc-settings.desktop

echo "${APP_NAME} has been removed. Batocera's Control Center is back."
