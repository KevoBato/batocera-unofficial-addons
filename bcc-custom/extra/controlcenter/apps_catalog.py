# apps_catalog.py - the apps the Control Center's Apps tab can start
# This file is part of the batocera distribution (https://batocera.org).
# Copyright (c) 2025-2026 lbrpdx for the Batocera team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License
# as published by the Free Software Foundation, version 3.
#
# YOU MUST KEEP THIS HEADER AS IT IS
#
# Shared by the Apps tab (AppsPanel.py) and BCC Settings (bcc-settings.py).
# Standard library only, no GTK.
#
# discover()  every app found on the system, from:
#   port      EmulationStation's Ports (/userdata/roms/ports, where BUA puts
#             its add-ons), names and pictures from gamelist.xml
#   flatpak   installed Flatpaks (EmulationStation's Flatpak system too)
#   appimage  AppImages in /userdata/system/add-ons/*/ that no port or
#             desktop entry starts already
#   desktop   .desktop entries (apps, not emulator config tools)
# load()/save()  the apps chosen for the tab: APPS_FILE, a JSON list
# launch()  start an app in its own window, or show it if it runs already
import os
import re
import json
import glob
import fnmatch
import shlex
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

APPS_FILE = "/userdata/system/configs/controlcenter/apps.json"
PORTS_DIR = "/userdata/roms/ports"
FLATPAK_DIR = "/userdata/roms/flatpak"
ADDONS_DIR = "/userdata/system/add-ons"
DESKTOP_DIRS = ["/usr/share/applications",
                "/userdata/system/.local/share/applications"]
FLATPAK_EXPORTS = ["/userdata/saves/flatpak/binaries/exports",
                   "/var/lib/flatpak/exports"]
LABWC_RC = "/userdata/system/.config/labwc/rc.xml"
LOG_FILE = "/userdata/system/logs/bcc-apps.log"

# Desktop entries that are not apps someone would start from a menu
_DESKTOP_SKIP = re.compile(r"(-config|-pref|-prefs|xinput_calibrator|view-eslog|"
                           r"org\.freedesktop\.Xwayland|file-roller-mimics|lxshortcut|"
                           r"libfm-pref-apps|pcmanfm-desktop-pref)\.desktop$")


def _app(source, key, name, icon, exec_, path=""):
    return {"id": f"{source}:{key}", "source": source, "name": name,
            "icon": icon or "", "exec": exec_, "path": path}


def _gamelist(folder: str) -> dict:
    """path (absolute) -> {name, image, hidden} from an ES gamelist.xml"""
    out = {}
    try:
        root = ET.parse(os.path.join(folder, "gamelist.xml")).getroot()
    except Exception:
        return out
    for g in root.iter("game"):
        p = (g.findtext("path") or "").strip()
        if not p:
            continue
        p = os.path.normpath(os.path.join(folder, p))
        img = (g.findtext("image") or g.findtext("thumbnail") or "").strip()
        if img:
            img = os.path.normpath(os.path.join(folder, img))
        out[p] = {"name": (g.findtext("name") or "").strip(),
                  "image": img if img and os.path.exists(img) else "",
                  "hidden": (g.findtext("hidden") or "").strip() == "true"}
    return out


def _ports():
    meta = _gamelist(PORTS_DIR)
    apps = []
    for path in sorted(glob.glob(os.path.join(PORTS_DIR, "*.sh"))):
        m = meta.get(path, {})
        if m.get("hidden"):
            continue
        name = m.get("name") or os.path.splitext(os.path.basename(path))[0]
        apps.append(_app("port", os.path.basename(path), name, m.get("image", ""),
                         f"bash {shlex.quote(path)}", path))
    return apps


def _flatpak_icon(app_id: str) -> str:
    for base in FLATPAK_EXPORTS:
        for size in ("256x256", "512x512", "128x128", "scalable", "64x64"):
            for ext in ("png", "svg"):
                p = f"{base}/share/icons/hicolor/{size}/apps/{app_id}.{ext}"
                if os.path.exists(p):
                    return p
    return ""


def _flatpaks():
    try:
        out = subprocess.run(["flatpak", "list", "--app", "--columns=application,name"],
                             capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return []
    installed = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0].strip():
            installed[parts[0].strip()] = parts[1].strip() if len(parts) > 1 else parts[0]
    # ES's Flatpak system names and pictures, by app id
    es = {}
    meta = _gamelist(FLATPAK_DIR)
    for path in glob.glob(os.path.join(FLATPAK_DIR, "*.flatpak")):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                app_id = f.read(256).strip().splitlines()[0].strip()
        except Exception:
            continue
        m = meta.get(path, {})
        if app_id and not m.get("hidden"):
            es[app_id] = m
    apps = []
    for app_id, name in sorted(installed.items(), key=lambda kv: kv[1].lower()):
        m = es.get(app_id, {})
        icon = m.get("image") or _flatpak_icon(app_id)
        a = _app("flatpak", app_id, m.get("name") or name, icon,
                 f"flatpak run {shlex.quote(app_id)}")
        a["app_id"] = app_id  # most Flatpaks use it for their window
        apps.append(a)
    return apps


def _desktop_files():
    files = {}
    dirs = DESKTOP_DIRS + [f"{b}/share/applications" for b in FLATPAK_EXPORTS]
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*.desktop")):
            files[os.path.basename(p)] = p  # later folders win
    return files


def parse_desktop(path: str) -> dict:
    """The [Desktop Entry] keys of a .desktop file"""
    keys, in_entry = {}, False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_entry = line == "[Desktop Entry]"
                elif in_entry and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys.setdefault(k.strip(), v.strip())
    except Exception:
        pass
    return keys


def _desktop_exec(value: str) -> str:
    # drop the field codes (%f, %U...) a menu would fill in
    return re.sub(r"\s*%[fFuUdDnNickvm]", "", value).replace("%%", "%").strip()


def _desktops():
    apps = []
    for base, path in sorted(_desktop_files().items()):
        if _DESKTOP_SKIP.search(base):
            continue
        d = parse_desktop(path)
        if d.get("Type", "Application") != "Application" or not d.get("Exec"):
            continue
        if d.get("NoDisplay", "").lower() == "true" or d.get("Hidden", "").lower() == "true":
            continue
        if d.get("Terminal", "").lower() == "true":
            continue
        a = _app("desktop", base, d.get("Name", base[:-8]), d.get("Icon", ""),
                 _desktop_exec(d["Exec"]), path)
        if d.get("StartupWMClass"):
            a["app_id"] = d["StartupWMClass"]
        apps.append(a)
    return apps


def _launch_script_for(folder: str, appimage: str) -> str:
    """An add-on's own launcher next to its AppImage (eglantine-launch.sh)"""
    for p in sorted(glob.glob(os.path.join(folder, "*.sh"))):
        # launch.sh, eglantine-launch.sh, start.sh, run.sh, app-launcher.sh;
        # not helpers like create-quiver-launchers.sh
        if re.search(r"(^|[-_])(launch|start|run)(er)?\.sh$", os.path.basename(p).lower()):
            return p
    return ""


def appimage_entry(path: str, name: str = "", icon: str = "", args: str = "") -> dict:
    """A catalog entry for one AppImage (also for ones added by hand)"""
    folder = os.path.dirname(path)
    if not name:
        name = re.sub(r"[-_.]?(x86_64|aarch64|amd64|arm64)$", "",
                      os.path.splitext(os.path.basename(path))[0], flags=re.I)
        name = name.replace("-", " ").replace("_", " ").strip().title() or path
    if not icon:
        pngs = [p for p in glob.glob(os.path.join(folder, "*.png")) + glob.glob(os.path.join(folder, "*.svg"))]
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        pngs.sort(key=lambda p: (stem not in os.path.basename(p).lower(), len(p)))
        icon = pngs[0] if pngs else ""
    script = _launch_script_for(folder, path)
    if script:
        exec_ = f"bash {shlex.quote(script)}"
    else:
        # Electron AppImages refuse to run as root without --no-sandbox;
        # others ignore an option they do not know only if told to, so it
        # is up to the user (args) in BCC Settings
        exec_ = f"{shlex.quote(path)} {args}".strip()
    return _app("appimage", path, name, icon, exec_, path)


def _appimages(already_started: str):
    apps = []
    for path in sorted(glob.glob(os.path.join(ADDONS_DIR, "*", "*.AppImage")) +
                       glob.glob(os.path.join(ADDONS_DIR, "*", "*.appimage"))):
        folder = os.path.dirname(path)
        # skip the ones a port or a desktop entry starts: those are listed
        if path in already_started or re.search(re.escape(folder) + r"([\"'/\s]|$)", already_started):
            continue
        apps.append(appimage_entry(path))
    return apps


def discover() -> list:
    """Every app found, grouped by source"""
    ports = _ports()
    flatpaks = _flatpaks()
    desktops = _desktops()
    started = ""
    for a in ports:
        try:
            with open(a["path"], encoding="utf-8", errors="replace") as f:
                started += f.read(20000)
        except Exception:
            pass
    for a in desktops:
        started += " " + a["exec"]
    # Flatpaks export a desktop entry of their own: list them once
    fp_ids = {a["app_id"] for a in flatpaks}
    desktops = [a for a in desktops
                if not any("flatpak run" in a["exec"] and i in a["exec"] for i in fp_ids)
                and a["id"][len("desktop:"):-len(".desktop")] not in fp_ids]
    return ports + flatpaks + _appimages(started) + desktops


# ---- the apps chosen for the tab ----
def load() -> list | None:
    """The chosen apps, or None when BCC Settings never saved a choice"""
    try:
        with open(APPS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [a for a in data.get("apps", []) if a.get("exec") and a.get("name")]
    except FileNotFoundError:
        return None
    except Exception:
        return []


def save(apps: list):
    os.makedirs(os.path.dirname(APPS_FILE), exist_ok=True)
    tmp = APPS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "apps": apps}, f, indent=2)
    os.replace(tmp, APPS_FILE)


def default_apps() -> list:
    """Before anything is chosen: ports, Flatpaks and AppImages"""
    return [a for a in discover() if a["source"] != "desktop"]


def remember_app_id(app_entry_id: str, app_id: str):
    """Save the window id an app turned out to use (see launch())"""
    apps = load()
    if not apps:
        return
    for a in apps:
        if a.get("id") == app_entry_id and a.get("app_id") != app_id:
            a["app_id"] = app_id
            save(apps)
            return


# ---- windows ----
def _wl_env() -> dict:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", "/var/run")
    if not env.get("WAYLAND_DISPLAY"):
        for s in ("wayland-0", "wayland-1"):
            if os.path.exists(os.path.join(env["XDG_RUNTIME_DIR"], s)):
                env["WAYLAND_DISPLAY"] = s
                break
    env.setdefault("DISPLAY", ":0.0")
    return env


def is_wayland() -> bool:
    return bool(_wl_env().get("WAYLAND_DISPLAY"))


def windows() -> list:
    """[(app_id, title)] of the open windows (labwc: wlrctl)"""
    try:
        out = subprocess.run(["wlrctl", "toplevel", "list"], capture_output=True,
                             text=True, timeout=3, env=_wl_env()).stdout
    except Exception:
        return []
    res = []
    for line in out.splitlines():
        if ":" in line:
            app_id, title = line.split(":", 1)
            res.append((app_id.strip(), title.strip()))
    return res


def running_ids(apps: list) -> set:
    """Entry ids of the apps that have a window open"""
    open_ids = {w[0].lower() for w in windows()}
    return {a["id"] for a in apps if a.get("app_id") and a["app_id"].lower() in open_ids}


def focus(app_id: str) -> bool:
    try:
        r = subprocess.run(["wlrctl", "toplevel", "focus", f"app_id:{app_id}"],
                           capture_output=True, timeout=3, env=_wl_env())
        return r.returncode == 0
    except Exception:
        return False


def close(app_id: str) -> bool:
    try:
        r = subprocess.run(["wlrctl", "toplevel", "close", f"app_id:{app_id}"],
                           capture_output=True, timeout=3, env=_wl_env())
        return r.returncode == 0
    except Exception:
        return False


def ensure_title_bar(app_id: str) -> bool:
    """Batocera's labwc removes every window's title bar. Give this app's
    windows one (close, minimize, maximize) so they can be closed and moved.
    Batocera rewrites rc.xml at boot, so this runs at each launch.
    True when rc.xml changed (labwc then re-reads it)."""
    if not app_id or not os.path.exists(LABWC_RC):
        return False
    try:
        with open(LABWC_RC, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return False
    # a rule giving it a title bar already (an add-on's own, like firefox*),
    # other than Batocera's identifier="*" that removes them all
    for tag in re.findall(r"<windowRule\b[^>]*>", text):
        ident = re.search(r'identifier="([^"]*)"', tag)
        if (ident and ident.group(1) != "*" and 'serverDecoration="yes"' in tag
                and fnmatch.fnmatch(app_id.lower(), ident.group(1).lower())):
            return False
    rule = '<windowRule identifier="%s" serverDecoration="yes" />' % app_id.replace('"', "")
    m = re.search(r"\n([ \t]*)</windowRules>", text)
    if m:
        # last rule wins in labwc: after Batocera's identifier="*" one
        indent = m.group(1)
        text = text[:m.start()] + f"\n{indent}  {rule}\n{indent}</windowRules>" + text[m.end():]
    elif "</labwc_config>" in text:
        text = text.replace("</labwc_config>",
                            "  <windowRules>\n    " + rule + "\n  </windowRules>\n</labwc_config>", 1)
    else:
        return False
    try:
        with open(LABWC_RC + ".tmp", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(LABWC_RC + ".tmp", LABWC_RC)
        subprocess.run(["sh", "-c", "kill -HUP $(pidof labwc)"], timeout=3)
    except Exception:
        return False
    return True


# The pointer: Batocera hides it (labwc HideCursor) while EmulationStation
# or a game is in front, and emulatorlauncher shows it for apps it starts.
# The Apps tab does the same: shown while an app it started has a window,
# hidden again once the last one closes.
_open_apps = set()   # window ids of the apps started from here, still open
_open_lock = threading.Lock()


def mouse(show: bool):
    try:
        subprocess.run(["batocera-mouse", "show" if show else "hide"],
                       env=_wl_env(), timeout=5, capture_output=True)
    except Exception:
        pass


def _track(app_id: str):
    """Hide the pointer again when the last app started from here closes"""
    with _open_lock:
        if app_id in _open_apps:
            return
        _open_apps.add(app_id)

    def wait_closed():
        gone = 0
        while True:
            time.sleep(2)
            if app_id.lower() in {w[0].lower() for w in windows()}:
                gone = 0
                continue
            gone += 1
            if gone < 2:  # some apps swap windows while starting
                continue
            with _open_lock:
                _open_apps.discard(app_id)
                last = not _open_apps
            if last:
                mouse(False)
            return
    threading.Thread(target=wait_closed, daemon=True).start()


def launch(app: dict, on_window=None) -> str:
    """Start the app in its own window, or bring its window to the front if
    it is open. Returns "focused" or "started". on_window(app_id) is called
    (from a thread) once a new window shows up."""
    app_id = app.get("app_id", "")
    if app_id and app_id.lower() in {w[0].lower() for w in windows()}:
        if focus(app_id):
            mouse(True)
            _track(app_id)
            return "focused"
    if app_id:
        ensure_title_bar(app_id)
    before = {w[0] for w in windows()}
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    log = open(LOG_FILE, "a")
    log.write(f"\n{time.ctime()}: {app.get('name')}: {app['exec']}\n")
    log.flush()
    subprocess.Popen(["setsid", "sh", "-c", app["exec"]], env=_wl_env(),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                     cwd=os.path.dirname(app.get("path") or "") or "/userdata",
                     start_new_session=True)
    log.close()
    mouse(True)

    def watch():
        # learn which window is the app's, for focus, "running" and the title bar
        for _ in range(120):
            time.sleep(0.5)
            new = [w for w in windows() if w[0] and w[0] not in before]
            if new:
                found = new[0][0]
                if found != app_id:
                    remember_app_id(app["id"], found)
                    if ensure_title_bar(found):
                        pass  # takes effect on the next window it opens
                _track(found)
                if on_window:
                    on_window(found)
                return
        # no window after a minute: nothing to show the pointer for
        with _open_lock:
            last = not _open_apps
        if last:
            mouse(False)
    threading.Thread(target=watch, daemon=True).start()
    return "started"


if __name__ == "__main__":
    for a in discover():
        print(f"{a['source']:9} {a['name'][:30]:30} {a['icon'][:50]:50} {a['exec'][:70]}")
