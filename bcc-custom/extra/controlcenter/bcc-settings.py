#!/usr/bin/env python3
# bcc-settings.py - BCC Settings: set up the Batocera Control Center
# This file is part of the batocera distribution (https://batocera.org).
# Copyright (c) 2025-2026 lbrpdx for the Batocera team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License
# as published by the Free Software Foundation, version 3.
#
# YOU MUST KEEP THIS HEADER AS IT IS
#
# A desktop app (F1 > Applications > BCC Settings), used with a mouse:
#   Apps   which apps the Apps tab shows, in which order; AppImages by hand
#   Tabs   the tabs to show (controlcenter.hiddentabs)
#   Theme  color, background, position (controlcenter.color/.background/.position)
# Save writes them all and restarts the Control Center (hidden) to apply them.
import os
import sys
import shlex
import subprocess

script_dir = os.path.dirname(os.path.realpath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import gi
gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

import apps_catalog
from xml_utils import parse_xml, list_tabs

APP_ID = "bcc-settings"
SOURCES = {"port": "Port", "flatpak": "Flatpak", "appimage": "AppImage", "desktop": "Desktop", "manual": "AppImage"}
COLORS = [("blue", "Blue (default)"), ("orange", "Orange"), ("purple", "Purple"), ("green", "Green"),
          ("pink", "Pink"), ("red", "Red"), ("yellow", "Yellow")]
BACKGROUNDS = [("dark", "Dark (default)"), ("tinted", "Tinted with the theme color")]
POSITIONS = [("center", "Center (default)"), ("left", "Side panel, left"), ("right", "Side panel, right")]
# Tabs the Control Center shows only when they apply: not worth hiding
CONDITIONAL_NOTE = {"Game": "only during a game", "Gun": "only for gun games"}


def setting_get(key):
    try:
        r = subprocess.run(["batocera-settings-get", key], capture_output=True, text=True, timeout=3)
        return (r.stdout or "").strip() or None
    except Exception:
        return None


def setting_set(key, value):
    subprocess.run(["batocera-settings-set", key, value], timeout=5)


def bcc_xml_path():
    for p in ("/userdata/system/configs/controlcenter/controlcenter.xml",
              "/usr/share/batocera/controlcenter/controlcenter.xml",
              os.path.join(script_dir, "controlcenter.xml")):
        if os.path.exists(p):
            return p
    return ""


def restart_bcc():
    """The way the BCC's own service restarts it: the hotkey then finds it"""
    subprocess.Popen(["sh", "-c",
                      "P=$(cat /var/run/batocera-controlcenter.pid 2>/dev/null); "
                      "[ -n \"$P\" ] && kill $P; rm -f /var/run/batocera-controlcenter.pid; "
                      "sleep 1; setsid batocera-controlcenter hidden >/dev/null 2>&1 &"],
                     start_new_session=True)


def icon_image(icon, size=32):
    pb = None
    try:
        if icon and os.path.isabs(icon) and os.path.exists(icon):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon, size, size, True)
        elif icon:
            pb = Gtk.IconTheme.get_default().load_icon(icon, size, Gtk.IconLookupFlags.FORCE_SIZE)
    except Exception:
        pb = None
    if pb is None:
        img = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DND)
    else:
        img = Gtk.Image.new_from_pixbuf(pb)
    img.set_size_request(size, size)
    return img


def app_row(app):
    row = Gtk.ListBoxRow()
    row.app = app
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.set_border_width(6)
    box.pack_start(icon_image(app.get("icon", "")), False, False, 0)
    name = Gtk.Label(label=app.get("name", ""), xalign=0)
    name.set_ellipsize(Pango.EllipsizeMode.END)
    box.pack_start(name, True, True, 0)
    tag = Gtk.Label(label=SOURCES.get(app.get("source"), app.get("source", "")))
    tag.get_style_context().add_class("dim-label")
    box.pack_end(tag, False, False, 0)
    row.add(box)
    row.set_tooltip_text(app.get("exec", ""))
    return row


class AppImageDialog(Gtk.Dialog):
    """Name, icon and options for an AppImage added by hand"""
    def __init__(self, parent, path):
        super().__init__(title="Add an AppImage", transient_for=parent, modal=True)
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Add", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        guess = apps_catalog.appimage_entry(path)
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        grid.set_border_width(12)
        self.name = Gtk.Entry(text=guess["name"], activates_default=True)
        self.icon = Gtk.FileChooserButton(title="Icon", action=Gtk.FileChooserAction.OPEN)
        f = Gtk.FileFilter(); f.set_name("Pictures"); f.add_mime_type("image/*")
        self.icon.add_filter(f)
        if guess["icon"]:
            self.icon.set_filename(guess["icon"])
        self.args = Gtk.Entry(placeholder_text="for example --no-sandbox")
        rows = [("File", Gtk.Label(label=path, xalign=0, selectable=True)),
                ("Name", self.name), ("Icon", self.icon), ("Options", self.args)]
        for i, (label, w) in enumerate(rows):
            grid.attach(Gtk.Label(label=label, xalign=1), 0, i, 1, 1)
            w.set_hexpand(True)
            grid.attach(w, 1, i, 1, 1)
        hint = Gtk.Label(xalign=0, wrap=True,
                         label="Electron apps (many AppImages) need --no-sandbox to run as root on Batocera.")
        hint.get_style_context().add_class("dim-label")
        grid.attach(hint, 1, len(rows), 1, 1)
        self.get_content_area().add(grid)
        self.path = path
        self.show_all()

    def entry(self):
        app = apps_catalog.appimage_entry(self.path, self.name.get_text().strip(),
                                          self.icon.get_filename() or "", self.args.get_text().strip())
        # always the AppImage itself (with the options), not an add-on script
        app["exec"] = f"{shlex.quote(self.path)} {self.args.get_text().strip()}".strip()
        app["source"] = "manual"
        app["id"] = "manual:" + self.path
        return app


class Settings(Gtk.Window):
    def __init__(self):
        super().__init__(title="BCC Settings")
        self.set_default_size(1100, 720)
        self.set_icon_name("preferences-system")
        self.dirty = False

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)
        self.info = Gtk.InfoBar()
        self.info.set_no_show_all(True)
        self.info_label = Gtk.Label(xalign=0)
        self.info.get_content_area().add(self.info_label)
        self.info.set_show_close_button(True)
        self.info.connect("response", lambda b, _r: b.hide())
        outer.pack_start(self.info, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        outer.pack_start(body, True, True, 0)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        side = Gtk.StackSidebar(stack=self.stack)
        side.set_size_request(160, -1)
        body.pack_start(side, False, False, 0)
        body.pack_start(self.stack, True, True, 0)
        self.stack.add_titled(self._apps_page(), "apps", "Apps")
        self.stack.add_titled(self._tabs_page(), "tabs", "Tabs")
        self.stack.add_titled(self._theme_page(), "theme", "Theme")

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_border_width(10)
        note = Gtk.Label(xalign=0, label="Save restarts the Control Center to apply the changes.")
        note.get_style_context().add_class("dim-label")
        bar.pack_start(note, True, True, 0)
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: self.close())
        save = Gtk.Button(label="Save")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", lambda *_: self.save())
        bar.pack_end(save, False, False, 0)
        bar.pack_end(close, False, False, 0)
        outer.pack_end(bar, False, False, 0)
        outer.pack_end(Gtk.Separator(), False, False, 0)

    def message(self, text, kind=Gtk.MessageType.INFO):
        self.info.set_message_type(kind)
        self.info_label.set_text(text)
        self.info.set_no_show_all(False)
        self.info.show_all()

    # ---- Apps ----
    def _apps_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        page.set_border_width(12)

        # left: everything found
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left.pack_start(Gtk.Label(label="<b>Found on this system</b>", use_markup=True, xalign=0), False, False, 0)
        tools = Gtk.Box(spacing=6)
        self.search = Gtk.SearchEntry(placeholder_text="Search")
        self.search.connect("search-changed", lambda *_: self.found.invalidate_filter())
        tools.pack_start(self.search, True, True, 0)
        self.source_filter = Gtk.ComboBoxText()
        for key, label in [("", "All sources"), ("port", "Ports (BUA add-ons)"), ("flatpak", "Flatpaks"),
                           ("appimage", "AppImages"), ("desktop", "Desktop entries")]:
            self.source_filter.append(key, label)
        self.source_filter.set_active_id("")
        self.source_filter.connect("changed", lambda *_: self.found.invalidate_filter())
        tools.pack_start(self.source_filter, False, False, 0)
        rescan = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        rescan.set_tooltip_text("Look for apps again")
        rescan.connect("clicked", lambda *_: self.load_found())
        tools.pack_start(rescan, False, False, 0)
        left.pack_start(tools, False, False, 0)
        self.found = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE)
        self.found.set_filter_func(self._found_filter)
        self.found.connect("row-activated", lambda *_: self.add_selected())
        left.pack_start(self._scrolled(self.found), True, True, 0)
        page.pack_start(left, True, True, 0)

        # middle: move buttons
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER)
        add = Gtk.Button(label="Add  →")
        add.connect("clicked", lambda *_: self.add_selected())
        remove = Gtk.Button(label="←  Remove")
        remove.connect("clicked", lambda *_: self.remove_selected())
        mid.pack_start(add, False, False, 0)
        mid.pack_start(remove, False, False, 0)
        page.pack_start(mid, False, False, 0)

        # right: the tab, in order
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right.pack_start(Gtk.Label(label="<b>In the Apps tab</b>", use_markup=True, xalign=0), False, False, 0)
        self.chosen = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.chosen.connect("row-activated", lambda *_: self.remove_selected())
        right.pack_start(self._scrolled(self.chosen), True, True, 0)
        order = Gtk.Box(spacing=6)
        for icon, tip, delta in [("go-up-symbolic", "Move up", -1), ("go-down-symbolic", "Move down", 1)]:
            b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda _b, d=delta: self.move_selected(d))
            order.pack_start(b, False, False, 0)
        add_ai = Gtk.Button(label="Add AppImage…")
        add_ai.connect("clicked", lambda *_: self.add_appimage())
        order.pack_end(add_ai, False, False, 0)
        right.pack_start(order, False, False, 0)
        page.pack_start(right, True, True, 0)

        chosen = apps_catalog.load()
        self.first_time = chosen is None
        for app in (chosen if chosen is not None else apps_catalog.default_apps()):
            self.chosen.add(app_row(app))
        self.load_found()
        if self.first_time:
            GLib.idle_add(lambda: self.message(
                "The Apps tab shows the ports, Flatpaks and AppImages found until you save a choice here.") and False)
        return page

    def _scrolled(self, child):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_shadow_type(Gtk.ShadowType.IN)
        sw.add(child)
        return sw

    def _chosen_ids(self):
        return {r.app["id"] for r in self.chosen.get_children()}

    def _found_filter(self, row):
        app = row.app
        if app["id"] in self._chosen_ids():
            return False
        src = self.source_filter.get_active_id() or ""
        if src and app["source"] != src:
            return False
        q = self.search.get_text().strip().lower()
        return not q or q in app["name"].lower() or q in app.get("exec", "").lower()

    def load_found(self):
        for r in self.found.get_children():
            self.found.remove(r)
        for app in apps_catalog.discover():
            self.found.add(app_row(app))
        self.found.show_all()
        self.found.invalidate_filter()

    def add_selected(self):
        for r in self.found.get_selected_rows():
            self.chosen.add(app_row(dict(r.app)))
        self.chosen.show_all()
        self.found.unselect_all()
        self.found.invalidate_filter()
        self.dirty = True

    def remove_selected(self):
        r = self.chosen.get_selected_row()
        if r:
            self.chosen.remove(r)
            self.found.invalidate_filter()
            self.dirty = True

    def move_selected(self, delta):
        r = self.chosen.get_selected_row()
        if not r:
            return
        i = r.get_index() + delta
        if 0 <= i < len(self.chosen.get_children()):
            self.chosen.remove(r)
            self.chosen.insert(r, i)
            self.chosen.select_row(r)
            self.dirty = True

    def add_appimage(self):
        dlg = Gtk.FileChooserDialog(title="Choose an AppImage", transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Choose", Gtk.ResponseType.OK)
        f = Gtk.FileFilter(); f.set_name("AppImages"); f.add_pattern("*.AppImage"); f.add_pattern("*.appimage")
        dlg.add_filter(f)
        a = Gtk.FileFilter(); a.set_name("All files"); a.add_pattern("*")
        dlg.add_filter(a)
        dlg.set_current_folder("/userdata" if os.path.isdir("/userdata") else os.path.expanduser("~"))
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.OK else None
        dlg.destroy()
        if not path:
            return
        try:
            os.chmod(path, os.stat(path).st_mode | 0o111)  # AppImages must be executable
        except Exception:
            pass
        d = AppImageDialog(self, path)
        if d.run() == Gtk.ResponseType.OK:
            self.chosen.add(app_row(d.entry()))
            self.chosen.show_all()
            self.dirty = True
        d.destroy()

    # ---- Tabs ----
    def _tabs_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(18)
        page.pack_start(Gtk.Label(label="<b>Tabs to show in the Control Center</b>", use_markup=True, xalign=0),
                        False, False, 0)
        hidden = set((setting_get("controlcenter.hiddentabs") or "").split(","))
        self.tab_checks = []
        try:
            tabs = list_tabs(parse_xml(bcc_xml_path()))
        except Exception:
            tabs = []
        for target, display in tabs:
            label = display + (f"  ({CONDITIONAL_NOTE[target]})" if target in CONDITIONAL_NOTE else "")
            cb = Gtk.CheckButton(label=label)
            cb.set_active(target not in hidden)
            cb.connect("toggled", lambda *_: self._tab_toggled())
            cb.target = target
            self.tab_checks.append(cb)
            page.pack_start(cb, False, False, 0)
        if not tabs:
            page.pack_start(Gtk.Label(label="The Control Center's tabs could not be read.", xalign=0), False, False, 0)
        return page

    def _tab_toggled(self):
        self.dirty = True
        # one tab always stays
        on = [c for c in self.tab_checks if c.get_active()]
        for c in self.tab_checks:
            c.set_sensitive(not (len(on) == 1 and c.get_active()))

    # ---- Theme ----
    def _theme_page(self):
        page = Gtk.Grid(column_spacing=14, row_spacing=12)
        page.set_border_width(18)
        page.attach(Gtk.Label(label="<b>Look of the Control Center</b>", use_markup=True, xalign=0), 0, 0, 2, 1)
        self.theme = {}
        for i, (key, label, choices) in enumerate([("controlcenter.color", "Color", COLORS),
                                                   ("controlcenter.background", "Background", BACKGROUNDS),
                                                   ("controlcenter.position", "Position", POSITIONS)], start=1):
            combo = Gtk.ComboBoxText()
            for value, text in choices:
                combo.append(value, text)
            cur = (setting_get(key) or choices[0][0]).lower()
            if not combo.set_active_id(cur):
                combo.set_active(0)
            combo.connect("changed", lambda *_: setattr(self, "dirty", True))
            page.attach(Gtk.Label(label=label, xalign=1), 0, i, 1, 1)
            page.attach(combo, 1, i, 1, 1)
            self.theme[key] = combo
        return page

    # ---- saving ----
    def save(self):
        try:
            apps = []
            for r in self.chosen.get_children():
                a = {k: v for k, v in r.app.items() if k in ("id", "source", "name", "icon", "exec", "path", "app_id")}
                apps.append(a)
            apps_catalog.save(apps)
            hidden = [c.target for c in self.tab_checks if not c.get_active()]
            setting_set("controlcenter.hiddentabs", ",".join(hidden))
            for key, combo in self.theme.items():
                setting_set(key, combo.get_active_id())
        except Exception as e:
            self.message(f"Could not save: {e}", Gtk.MessageType.ERROR)
            return
        restart_bcc()
        self.dirty = False
        self.message("Saved. The Control Center restarts with the new settings.")


def main():
    GLib.set_prgname(APP_ID)  # the window's app id on Wayland
    # Batocera's labwc removes every window's title bar: keep this one's
    apps_catalog.ensure_title_bar(APP_ID)
    win = Settings()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
