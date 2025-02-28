#!/bin/bash

# Step 1: Detect system architecture
echo "Detecting system architecture..."
arch=$(uname -m)

if [ "$arch" == "x86_64" ]; then
    echo "Architecture: x86_64 detected."
    appimage_url="https://github.com/cosmo0/arcade-manager/releases/download/v7.1/ArcadeManager-7.1-linux-x64.AppImage"
elif [ "$arch" == "aarch64" ]; then
    echo "Architecture: arm64 detected."
    appimage_url="https://github.com/cosmo0/arcade-manager/releases/download/v7.1/ArcadeManager-7.1-linux-arm64.AppImage"
else
    echo "Unsupported architecture: $arch. Exiting."
    exit 1
fi

# Step 2: Download the AppImage
echo "Downloading Arcade Manager AppImage from $appimage_url..."
mkdir -p /userdata/system/add-ons/arcade-manager
wget -q --show-progress -O /userdata/system/add-ons/arcade-manager/ArcadeManager.AppImage "$appimage_url"

if [ $? -ne 0 ]; then
    echo "Failed to download Arcade Manager AppImage."
    exit 1
fi

chmod a+x /userdata/system/add-ons/arcade-manager/ArcadeManager.AppImage
echo "Arcade Manager AppImage downloaded and marked as executable."

# Step 3: Create the Arcade Manager Script
echo "Creating Arcade Manager script in Ports..."
mkdir -p /userdata/roms/ports
cat << 'EOF' > /userdata/roms/ports/ArcadeManager.sh
#!/bin/bash

# Environment setup
export $(cat /proc/1/environ | tr '\0' '\n')
export DISPLAY=:0.0

# Directories and file paths
app_dir="/userdata/system/add-ons/arcade-manager"
app_image="${app_dir}/ArcadeManager.AppImage"
log_dir="/userdata/system/logs"
log_file="${log_dir}/arcade-manager.log"

# Ensure log directory exists
mkdir -p "${log_dir}"

# Append all output to the log file
exec &> >(tee -a "$log_file")
echo "$(date): Launching Arcade Manager"

# Launch Arcade Manager AppImage
if [ -x "${app_image}" ]; then
    cd "${app_dir}"
    ./ArcadeManager.AppImage > "${log_file}" 2>&1
    echo "Arcade Manager exited."
else
    echo "ArcadeManager.AppImage not found or not executable."
    exit 1
fi
EOF

chmod +x /userdata/roms/ports/ArcadeManager.sh

# Step 4: Refresh the Ports menu
echo "Refreshing Ports menu..."
curl http://127.0.0.1:1234/reloadgames

# Download the image
echo "Downloading Arcade Manager logo..."
curl -L -o /userdata/roms/ports/images/ArcadeManager_Logo.png https://github.com/DTJW92/batocera-unofficial-addons/raw/main/arcademanager/extra/icon.png

echo "Adding logo to Arcade Manager entry in gamelist.xml..."
xmlstarlet ed -s "/gameList" -t elem -n "game" -v "" \
  -s "/gameList/game[last()]" -t elem -n "path" -v "./ArcadeManager.sh" \
  -s "/gameList/game[last()]" -t elem -n "name" -v "ArcadeManager" \
  -s "/gameList/game[last()]" -t elem -n "image" -v "./images/ArcadeManager_Logo.png" \
  /userdata/roms/ports/gamelist.xml > /userdata/roms/ports/gamelist.xml.tmp && mv /userdata/roms/ports/gamelist.xml.tmp /userdata/roms/ports/gamelist.xml


curl http://127.0.0.1:1234/reloadgames

echo
echo "Installation complete! You can now launch Arcade Manager from the Ports menu."
