#!/usr/bin/env python3
"""Apply the Switch 2 settings chosen in EmulationStation (per game or for
the whole system) to Eglantine's qt-config.ini before a game starts.

A setting left on its default in ES gets back the emulator's own value, the
one set in Eglantine's window, so ES choices for one game don't leak into
the next. If that value is changed in Eglantine's window in the meantime,
the new value is kept.

Usage: eglantine-settings.py <game folder>   (no game: only restore)
"""
import json
import os
import re
import sys

BATOCERA_CONF = "/userdata/system/batocera.conf"
QT_CONFIG = "/userdata/system/.config/eden/qt-config.ini"
STATE_FILE = "/userdata/system/add-ons/eglantine/settings-state.json"
SYSTEM = "switch2"

# ES option -> qt-config.ini (section, key). ES choice values are the
# emulator's own values (enum numbers or true/false), written unchanged.
OPTIONS = {
    "eglantine_console_mode": ("System", "use_docked_mode"),
    "eglantine_memory_layout": ("Core", "memory_layout_mode"),
    "eglantine_language": ("System", "language_index"),
    "eglantine_region": ("System", "region_index"),
    "eglantine_backend": ("Renderer", "backend"),
    "eglantine_resolution": ("Renderer", "resolution_setup"),
    "eglantine_vsync": ("Renderer", "use_vsync"),
    "eglantine_scaling_filter": ("Renderer", "scaling_filter"),
    "eglantine_fsr_sharpness": ("Renderer", "fsr_sharpening_slider"),
    "eglantine_anti_aliasing": ("Renderer", "anti_aliasing"),
    "eglantine_aspect_ratio": ("Renderer", "aspect_ratio"),
    "eglantine_frame_gen": ("Renderer", "frame_gen"),
    "eglantine_frame_gen_type": ("Renderer", "frame_gen_type"),
    "eglantine_frame_gen_multiplier": ("Renderer", "frame_gen_multiplier"),
    "eglantine_gpu_accuracy": ("Renderer", "gpu_accuracy"),
    "eglantine_dma_accuracy": ("Renderer", "dma_accuracy"),
    "eglantine_async_shaders": ("Renderer", "use_asynchronous_shaders"),
    "eglantine_disk_shader_cache": ("Renderer", "use_disk_shader_cache"),
    "eglantine_anisotropy": ("Renderer", "max_anisotropy"),
    "eglantine_astc_decode": ("Renderer", "accelerate_astc"),
    "eglantine_astc_recompression": ("Renderer", "astc_recompression"),
    "eglantine_vram_usage": ("Renderer", "vram_usage_mode"),
    "eglantine_nvdec": ("Renderer", "nvdec_emulation"),
    "eglantine_frame_pacing": ("Renderer", "frame_pacing_mode"),
    "eglantine_dyna_state": ("Renderer", "dyna_state"),
    "eglantine_cpu_accuracy": ("Cpu", "cpu_accuracy"),
    "eglantine_multicore": ("Core", "use_multi_core"),
    "eglantine_use_speed_limit": ("Core", "use_speed_limit"),
    "eglantine_speed_limit": ("Core", "speed_limit"),
}


def es_settings(game):
    """The eglantine_* options from batocera.conf: the game's own, else the
    system's."""
    name = os.path.basename(game.rstrip("/"))
    system, per_game = {}, {}
    game_line = re.compile(r'^' + SYSTEM + r'\["(.*)"\]\.(eglantine_\w+)=(.*)$')
    system_line = re.compile(r'^' + SYSTEM + r'\.(eglantine_\w+)=(.*)$')
    try:
        with open(BATOCERA_CONF, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                m = game_line.match(line)
                if m:
                    if name and m.group(1) == name:
                        per_game[m.group(2)] = m.group(3)
                    continue
                m = system_line.match(line)
                if m:
                    system[m.group(1)] = m.group(2)
    except OSError:
        pass
    merged = {**system, **per_game}
    return {k: v.strip() for k, v in merged.items() if k in OPTIONS and v.strip() not in ("", "auto", "default")}


class QtIni:
    """Line-based editing of qt-config.ini that keeps everything else as is.
    Each setting is two lines: key\\default=true|false and key=value."""

    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                self.lines = f.read().splitlines()
        except OSError:
            self.lines = []

    def _section(self, section):
        """(index of the header, index after the section's last line)"""
        start = None
        for i, line in enumerate(self.lines):
            if line.strip() == f"[{section}]":
                start = i
            elif start is not None and line.startswith("["):
                return start, i
        return (start, len(self.lines)) if start is not None else (None, None)

    def _find(self, section, key):
        start, end = self._section(section)
        if start is None:
            return None
        for i in range(start + 1, end):
            if self.lines[i].startswith(key + "="):
                return i
        return None

    def get(self, section, key):
        """(value, default flag) or None when the key is not there."""
        i = self._find(section, key)
        if i is None:
            return None
        value = self.lines[i].split("=", 1)[1]
        j = self._find(section, key + "\\default")
        default = self.lines[j].split("=", 1)[1] if j is not None else None
        return [value, default]

    def set(self, section, key, value, default):
        start, end = self._section(section)
        if start is None:
            self.lines += ["", f"[{section}]"]
            start, end = len(self.lines) - 1, len(self.lines)
        for name, val in ((key + "\\default", default), (key, value)):
            if val is None:
                continue
            i = self._find(section, name)
            if i is None:
                self.lines.insert(start + 1, f"{name}={val}")
            else:
                self.lines[i] = f"{name}={val}"

    def remove(self, section, key):
        for name in (key, key + "\\default"):
            i = self._find(section, name)
            if i is not None:
                del self.lines[i]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines) + "\n")
        os.replace(tmp, self.path)


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else ""
    wanted = es_settings(game) if game else {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}

    ini = QtIni(QT_CONFIG)
    changed = False
    for option, (section, key) in OPTIONS.items():
        cur = ini.get(section, key)
        cur_value = cur[0] if cur else None
        saved = state.get(option)
        value = wanted.get(option)
        if value is not None:
            # Remember the emulator's own value, unless this is still the value
            # written for an earlier game
            base = cur if saved is None or cur_value != saved["written"] else saved["base"]
            if cur_value != value or (cur and cur[1] != "false"):
                ini.set(section, key, value, "false")
                changed = True
            state[option] = {"base": base, "written": value}
            print(f"[eglantine] {section}/{key}={value} (from EmulationStation)")
        elif saved is not None:
            # Back to the emulator's own value, unless it was changed in
            # Eglantine's window since
            if cur_value == saved["written"]:
                if saved["base"] is None:
                    ini.remove(section, key)
                else:
                    ini.set(section, key, saved["base"][0], saved["base"][1])
                changed = True
            del state[option]

    if changed:
        ini.save()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


if __name__ == "__main__":
    main()
