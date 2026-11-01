#!/bin/bash
# Installer for Eglantine, an experimental Switch 2 emulator (the PokeDinner
# fork of Eden). Installs the latest Linux AppImage to
# /userdata/system/add-ons/eglantine and adds a Nintendo Switch 2 system to
# EmulationStation (Hotkey+Start exits), with the emulator's main settings in
# ES's per-game and system settings. The emulator's own window opens from the
# "Eglantine (emulator)" entry in that list and from F1 > Applications.
# Games go in /userdata/roms/switch2, one folder per game named "<Game>.sw2"
# holding the dump (base/exefs/main, base/romfs, ...).
# Batocera 44 replaced configgen/emulatorlauncher with batocera-launch, which
# finds emulators through Python entry points, so the installer reads the
# Batocera version and installs the matching launcher.
# Optional: EGLANTINE_URL=<direct .AppImage link> to install a specific build.

# Variables
install_dir="/userdata/system/add-ons/eglantine"
es_config_dir="/userdata/system/configs/emulationstation"
rom_dir="/userdata/roms/switch2"
batocera_conf="/userdata/system/batocera.conf"
# Python's per-user site-packages, as seen by EmulationStation (HOME=/userdata/system)
user_site=$(HOME=/userdata/system python3 -c 'import site; print(site.getusersitepackages())')
base_url="https://github.com/batocera-unofficial-addons/batocera-unofficial-addons/raw/main/eglantine"
bua_url="https://github.com/batocera-unofficial-addons/batocera-unofficial-addons/raw/main/app"
releases_api="https://git.eden-emu.dev/api/v1/repos/Franseven/PokeDinner-a-Eglantine-Fork/releases?limit=15"

fail() {
    echo "$1"
    rm -f "$install_dir/eglantine.AppImage.tmp"
    exit 1
}

# set_conf key value: add or update a line in batocera.conf
set_conf() {
    if grep -q "^$1=" "$batocera_conf" 2>/dev/null; then
        sed -i "s|^$1=.*|$1=$2|" "$batocera_conf"
    else
        [ -f "$batocera_conf" ] && [ -n "$(tail -c1 "$batocera_conf")" ] && echo >> "$batocera_conf"
        echo "$1=$2" >> "$batocera_conf"
    fi
}

if [ "$(uname -m)" != "x86_64" ]; then
    fail "Eglantine only has x86_64 Linux builds. This machine is $(uname -m)."
fi

# Pick the launcher by Batocera version: 44 and later use batocera-launch,
# 43 and earlier use configgen's emulatorlauncher.
batocera_version=$(batocera-version 2>/dev/null)
major=$(echo "$batocera_version" | grep -o '^[0-9]*')
echo "Batocera version: ${batocera_version:-unknown}"
[ -n "$major" ] || fail "Could not read the Batocera version."
if [ "$major" -ge 44 ]; then
    launcher="batocera-launch"
    package="batocera_launch.emulator"
else
    launcher="emulatorlauncher"
    package="configgen.generators"
fi
# Make sure that launcher is really there (early Batocera 44 test builds still
# had configgen). -I keeps the per-user folders and the current directory out,
# so only the system's own packages count.
python3 -I -c "import $package" 2>/dev/null \
    || fail "Batocera $major should have $launcher, but $package is missing. Eglantine was not installed."
echo "Launcher: $launcher"

# Ensure BUA Python hook is present (it lets emulatorlauncher find the generator)
if [ "$launcher" = "emulatorlauncher" ] && [ ! -f "$user_site/usercustomize.py" ]; then
    echo "Installing BUA Python hook..."
    mkdir -p "$user_site"
    wget -q --show-progress -O "$user_site/usercustomize.py" "$bua_url/usercustomize.py"
fi

# Find the newest release with a Linux AppImage (some releases are Windows-only)
appimage_url="${EGLANTINE_URL:-}"
if [ -z "$appimage_url" ]; then
    echo "Fetching latest Eglantine release..."
    appimage_url=$(curl -fsSL "$releases_api" | python3 -c '
import json, sys
for rel in json.load(sys.stdin):
    for a in rel.get("assets", []):
        if a["name"].endswith("linux-x86_64.AppImage"):
            print(a["browser_download_url"])
            sys.exit(0)
')
    [ -n "$appimage_url" ] || fail "Failed to find an Eglantine Linux AppImage in the latest releases."
fi

# Download, keeping the old AppImage until the new one is complete
mkdir -p "$install_dir"
echo "Downloading $(basename "$appimage_url")..."
wget -q --show-progress -O "$install_dir/eglantine.AppImage.tmp" "$appimage_url" || fail "Failed to download Eglantine."
[ "$(head -c4 "$install_dir/eglantine.AppImage.tmp" | od -An -c | tr -d ' ')" = '177ELF' ] \
    || fail "The download is not an AppImage. Not installing."
mv -f "$install_dir/eglantine.AppImage.tmp" "$install_dir/eglantine.AppImage"
chmod +x "$install_dir/eglantine.AppImage"

# Download the launcher for this Batocera and the launch wrapper
if [ "$launcher" = "batocera-launch" ]; then
    # A package plus the dist-info that registers it as the "eglantine" emulator
    echo "Downloading batocera-launch emulator..."
    plugin_dir="$user_site/batocera_launch_eglantine"
    dist_info="$user_site/batocera_launch_eglantine-1.0.dist-info"
    mkdir -p "$plugin_dir" "$dist_info"
    wget -q --show-progress -O "$plugin_dir/__init__.py" "$base_url/launch/batocera_launch_eglantine/__init__.py" \
        || fail "Failed to download the batocera-launch emulator."
    printf 'Metadata-Version: 2.1\nName: batocera-launch-eglantine\nVersion: 1.0\n' > "$dist_info/METADATA"
    printf '[batocera_launch.emulators]\neglantine = batocera_launch_eglantine:Eglantine\n' > "$dist_info/entry_points.txt"
else
    echo "Downloading generator..."
    mkdir -p "$install_dir/generator/eglantine"
    wget -q --show-progress -O "$install_dir/generator/eglantine/__init__.py" "$base_url/generator/eglantine/__init__.py"
    wget -q --show-progress -O "$install_dir/generator/eglantine/eglantineGenerator.py" "$base_url/generator/eglantine/eglantineGenerator.py"
fi
wget -q --show-progress -O "$install_dir/eglantine-launch.sh" "$base_url/extra/eglantine-launch.sh" \
    || fail "Failed to download the launch wrapper."
wget -q --show-progress -O "$install_dir/eglantine-settings.py" "$base_url/extra/eglantine-settings.py" \
    || fail "Failed to download the settings helper."
chmod +x "$install_dir/eglantine-launch.sh" "$install_dir/eglantine-settings.py"

# The emulator's icon, for F1 > Applications and the Switch 2 list
icon_tmp=$(mktemp -d)
(cd "$icon_tmp" && "$install_dir/eglantine.AppImage" --appimage-extract eglantine.png >/dev/null 2>&1)
cp -f "$icon_tmp/squashfs-root/eglantine.png" "$install_dir/eglantine.png" 2>/dev/null
rm -rf "$icon_tmp"

# Download and deploy ES system, and the per-game settings shown in ES
echo "Downloading ES config..."
mkdir -p "$es_config_dir"
# The ROM folder may be a link to another drive, which can be unplugged
[ -L "$rom_dir" ] || mkdir -p "$rom_dir"
wget -q --show-progress -O "$es_config_dir/es_systems_switch2.cfg" "$base_url/extra/es_systems_switch2.cfg"
wget -q --show-progress -O "$es_config_dir/es_features_switch2.cfg" "$base_url/extra/es_features_switch2.cfg"
if [ "$launcher" = "batocera-launch" ]; then
    sed -i 's|<command>emulatorlauncher |<command>batocera-launch |' "$es_config_dir/es_systems_switch2.cfg"
fi

# An entry in the Switch 2 list that opens the emulator's own window. It is a
# file, not a folder like the games, so eglantine-launch.sh knows it apart.
if [ -d "$rom_dir" ]; then
    gamelist="$rom_dir/gamelist.xml"
    echo "Opens the Eglantine emulator itself, for keys, firmware, controllers and settings." > "$rom_dir/Eglantine.sw2"
    mkdir -p "$rom_dir/images"
    [ -f "$install_dir/eglantine.png" ] && cp -f "$install_dir/eglantine.png" "$rom_dir/images/eglantine.png"
    if [ ! -f "$gamelist" ]; then
        printf '<?xml version="1.0" encoding="UTF-8"?>\n<gameList>\n</gameList>\n' > "$gamelist"
    fi
    xmlstarlet ed -d "/gameList/game[path='./Eglantine.sw2']" \
      -s "/gameList" -t elem -n "game" -v "" \
      -s "/gameList/game[last()]" -t elem -n "path" -v "./Eglantine.sw2" \
      -s "/gameList/game[last()]" -t elem -n "name" -v "Eglantine (emulator)" \
      -s "/gameList/game[last()]" -t elem -n "desc" -v "Opens the Eglantine emulator itself, to set up keys, firmware, controllers and its own settings." \
      -s "/gameList/game[last()]" -t elem -n "image" -v "./images/eglantine.png" \
      "$gamelist" > "$gamelist.tmp" && mv "$gamelist.tmp" "$gamelist"
fi

# F1 > Applications entry. /usr/share/applications is reset at boot, so a copy
# is kept in /userdata and put back by custom.sh.
echo "Creating desktop entry..."
desktop_file="/usr/share/applications/Eglantine.desktop"
persistent_desktop="/userdata/system/configs/eglantine/Eglantine.desktop"
restore_script="/userdata/system/configs/eglantine/restore_desktop_entry.sh"
mkdir -p /userdata/system/configs/eglantine
cat > "$persistent_desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Eglantine (Switch 2)
Exec=$install_dir/eglantine-launch.sh
Icon=$install_dir/eglantine.png
Terminal=false
Categories=Game;batocera.linux;
DESKTOP
chmod +x "$persistent_desktop"
cp -f "$persistent_desktop" "$desktop_file"
chmod +x "$desktop_file"
cat > "$restore_script" <<RESTORE
#!/bin/bash
if [ ! -f "$desktop_file" ]; then
    cp "$persistent_desktop" "$desktop_file"
    chmod +x "$desktop_file"
fi
RESTORE
chmod +x "$restore_script"
touch /userdata/system/custom.sh
if ! grep -q "$restore_script" /userdata/system/custom.sh; then
    echo "bash \"$restore_script\" &" >> /userdata/system/custom.sh
fi
chmod +x /userdata/system/custom.sh
if [ -d "$rom_dir" ] && [ ! -e "$rom_dir/_info.txt" ]; then
    cat > "$rom_dir/_info.txt" <<'EOF'
Nintendo Switch 2 games for Eglantine.

Put each game's dump in its own folder ending in .sw2, for example:
  Mario Kart World.sw2/base/exefs/main
  Mario Kart World.sw2/base/romfs/...

Keys and firmware are set up in the emulator itself
(/userdata/system/.local/share/eden).
EOF
fi

# Batocera has no default emulator for switch2, so set it (without this:
# "emulator missing"). Bezels have no per-system menu for Switch 2, so turn them off.
set_conf switch2.emulator eglantine
set_conf switch2.core eglantine
set_conf switch2.bezel none

# Finish
echo "Eglantine installation complete. Put your Switch 2 games in $rom_dir,"
echo "one folder per game named <Game>.sw2."
echo "If a game exits right away, check /userdata/system/logs/eglantine.log"
killall -9 emulationstation
