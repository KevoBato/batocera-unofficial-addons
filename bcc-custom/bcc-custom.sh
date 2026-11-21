#!/bin/bash
# Installer for Modern Control Center: a modern look for Batocera's Control
# Center (Hotkey + east face button): icons, quick-settings tiles, a translucent rounded
# panel (on Batocera's Wayland desktop), soft cards, pill tabs and a clear
# glowing highlight for controller navigation.
#
# It is Batocera's own Control Center (github.com/lbrpdx/batocera-
# controlcenter, GPLv3) with small additions, installed in
# /userdata/system/add-ons/bcc-custom and laid over Batocera's copy by a
# service, so nothing in Batocera is changed. Batocera 43 and later.

APPNAME="Modern Control Center"
install_dir="/userdata/system/add-ons/bcc-custom"
app_dir="$install_dir/controlcenter"
service_file="/userdata/system/services/bcc_custom"
base_url="https://github.com/batocera-unofficial-addons/batocera-unofficial-addons/raw/main/bcc-custom"
user_configs="/userdata/system/configs/controlcenter"

fail() {
    echo "$1"
    exit 1
}

[ -d /usr/share/batocera/controlcenter ] || \
    fail "$APPNAME needs Batocera 43 or later (this Batocera has no Control Center)."

echo "Installing $APPNAME..."
mkdir -p "$app_dir"
for f in controlcenter.py ui_core.py xml_utils.py shell.py refresh.py log.py gamepads.py \
         DocViewer.py controlcenter.xml style.css bato-record.gif LICENSE; do
    wget -q --show-progress -O "$app_dir/$f" "$base_url/extra/controlcenter/$f" \
        || fail "Failed to download $f."
done
chmod +x "$app_dir/controlcenter.py"
wget -q --show-progress -O "$install_dir/bcc-custom-logo.png" "$base_url/extra/bcc-custom-logo.png"

# The service lays the add-on's Control Center over Batocera's at every boot
mkdir -p /userdata/system/services
wget -q --show-progress -O "$service_file" "$base_url/extra/bcc-custom-service" \
    || fail "Failed to download the service."
chmod +x "$service_file"
batocera-services enable bcc_custom >/dev/null 2>&1
# Reinstall/update: stop first so the new files are laid over cleanly
bash "$service_file" stop >/dev/null 2>&1
bash "$service_file" start || fail "Could not start $APPNAME."

echo ""
echo "$APPNAME is installed. Press Hotkey + the east (right) face button (B on Xbox-style controllers) to open the Control Center."
# Your own Control Center files win over any theme: say so if they exist
for f in controlcenter.xml style.css; do
    if [ -f "$user_configs/$f" ]; then
        echo "Note: you have your own $user_configs/$f, which Batocera uses instead of"
        echo "      $APPNAME's. Remove it to see the new $( [ "$f" = style.css ] && echo look || echo layout )."
    fi
done
