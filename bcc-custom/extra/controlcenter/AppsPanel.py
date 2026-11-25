# AppsPanel.py - the Apps tab: a grid of apps to start in a window
# This file is part of the batocera distribution (https://batocera.org).
# Copyright (c) 2025-2026 lbrpdx for the Batocera team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License
# as published by the Free Software Foundation, version 3.
#
# YOU MUST KEEP THIS HEADER AS IT IS
#
# <apps columns="4" iconsize="96" /> shows the apps chosen in BCC Settings
# (apps_catalog.APPS_FILE), or, before any choice, the ports, Flatpaks and
# AppImages found. Each line of the grid is one menu row: left/right picks
# an app, south starts it in its own window (the Control Center hides), or
# brings its window back to the front when it is already open.
import os
import gi
gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango
from log import debug_print
from refresh import run_off_main_thread
import apps_catalog

import locale
_ = locale.gettext

FALLBACK_ICON = "application-x-executable"


def _icon_pixbuf(icon: str, size: int):
    """A path, or an icon theme name (desktop entries), scaled to fit size"""
    try:
        if icon and os.path.isabs(icon) and os.path.exists(icon):
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(icon, size, size, True)
    except Exception as e:
        debug_print(f"[APPS] icon {icon}: {e}")
    theme = Gtk.IconTheme.get_default()
    for name in (icon, FALLBACK_ICON):
        if not name or os.path.isabs(name):
            continue
        try:
            pb = theme.load_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
            if pb:
                return pb
        except Exception:
            pass
    return None


class AppsPanel:
    def __init__(self, core, columns: int = 4, iconsize: int = 96):
        self.core = core
        self.columns = max(1, columns)
        self.iconsize = max(32, iconsize)
        self.apps = []
        self.rows = []
        self._mtime = None
        self._tiles = {}  # app id -> tile button

    # ---- building ----
    def build(self, parent: Gtk.Box):
        self.parent = parent
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.get_style_context().add_class("cc-apps")
        parent.pack_start(self.box, False, False, 3)
        self._fill()
        # check for a new choice of apps, and which ones run, each time the
        # Control Center opens
        if self.core.window is not None:
            self.core.window.connect("map", lambda *_: self.refresh())
        else:
            GLib.idle_add(self._connect_map)

    def _connect_map(self):
        if self.core.window is not None:
            self.core.window.connect("map", lambda *_: self.refresh())
        return False

    def _load(self):
        apps = apps_catalog.load()
        if apps is None:
            apps = apps_catalog.default_apps()
        try:
            self._mtime = os.path.getmtime(apps_catalog.APPS_FILE)
        except OSError:
            self._mtime = None
        return apps

    def _fill(self):
        self.apps = self._load()
        self._tiles = {}
        self.rows = []
        if not self.apps:
            msg = Gtk.Label(label=_("No apps yet. Choose them in BCC Settings (F1, Applications)."))
            msg.set_line_wrap(True)
            msg.get_style_context().add_class("item-text")
            self.box.pack_start(msg, False, False, 12)
            return
        for start in range(0, len(self.apps), self.columns):
            self.rows.append(self._build_row(self.apps[start:start + self.columns]))

    def _build_row(self, apps) -> Gtk.EventBox:
        row = Gtk.EventBox()
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        line.set_homogeneous(True)
        line.get_style_context().add_class("cc-apps-line")
        row.add(line)
        row._items = []
        for app in apps:
            tile = self._build_tile(app)
            line.pack_start(tile, True, True, 0)
            row._items.append(tile)
        # keep the grid aligned on a short last line
        for _i in range(self.columns - len(apps)):
            line.pack_start(Gtk.Box(), True, True, 0)
        row._item_index = 0
        row._on_left = None
        row._on_right = None
        row._on_activate = None
        self.core.register_row(row)
        self.box.pack_start(row, False, False, 0)
        return row

    def _build_tile(self, app) -> Gtk.Button:
        btn = Gtk.Button()
        btn.get_style_context().add_class("cc-app-tile")
        btn.set_can_focus(True)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        holder = Gtk.Box()
        holder.set_size_request(self.iconsize, self.iconsize)
        holder.set_halign(Gtk.Align.CENTER)
        pb = _icon_pixbuf(app.get("icon", ""), self.iconsize)
        img = Gtk.Image.new_from_pixbuf(pb) if pb else Gtk.Image.new_from_icon_name(FALLBACK_ICON, Gtk.IconSize.DIALOG)
        img.set_valign(Gtk.Align.CENTER)
        holder.set_center_widget(img)
        v.pack_start(holder, False, False, 0)
        lbl = Gtk.Label(label=app.get("name", ""))
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_max_width_chars(14)
        lbl.set_justify(Gtk.Justification.CENTER)
        v.pack_start(lbl, False, False, 0)
        # a dot under the name while the app has a window open
        dot = Gtk.Label(label="●")
        dot.get_style_context().add_class("cc-app-running-dot")
        dot.set_no_show_all(True)
        v.pack_start(dot, False, False, 0)
        btn._dot = dot
        btn.add(v)
        btn.set_tooltip_text(app.get("name", ""))
        btn.connect("clicked", lambda *_: self.open(app))
        self._tiles[app["id"]] = btn
        return btn

    # ---- keeping up to date ----
    def refresh(self):
        try:
            mtime = os.path.getmtime(apps_catalog.APPS_FILE)
        except OSError:
            mtime = None
        if mtime != self._mtime:
            self._rebuild()
        self._update_running()
        return False

    def _rebuild(self):
        old = self.rows
        for r in old:
            if r in self.core.focus_rows:
                self.core.unhighlight_row(r)
        for child in self.box.get_children():
            self.box.remove(child)
            child.destroy()
        # register_row appends to focus_rows: keep only the rows of the tab
        # that is shown (the tab switcher adds them back when it is shown)
        shown = any(r in self.core.focus_rows for r in old)
        for r in old:
            while r in self.core.focus_rows:
                self.core.focus_rows.remove(r)
        self._fill()
        tab_rows = getattr(self.parent, "_tab_rows", None)
        if tab_rows is not None:
            for r in old:
                while r in tab_rows:
                    tab_rows.remove(r)
            tab_rows.extend(self.rows)
        if not shown:
            for r in self.rows:
                while r in self.core.focus_rows:
                    self.core.focus_rows.remove(r)
        if self.core.focus_index >= len(self.core.focus_rows):
            self.core.focus_index = max(0, len(self.core.focus_rows) - 1)
        self.box.show_all()

    def _update_running(self):
        def work():
            ids = apps_catalog.running_ids(self.apps)
            GLib.idle_add(self._show_running, ids)
        run_off_main_thread(work)

    def _show_running(self, ids):
        for app_id, tile in self._tiles.items():
            on = app_id in ids
            tile._dot.set_visible(on)
            ctx = tile.get_style_context()
            (ctx.add_class if on else ctx.remove_class)("cc-app-running")
        return False

    # ---- starting ----
    def open(self, app):
        debug_print(f"[APPS] open {app.get('name')}")
        # the Control Center sits above every window: get out of the way
        self.core.hide()

        def work():
            try:
                apps_catalog.launch(app, on_window=lambda _id: GLib.idle_add(self._remember, app, _id))
            except Exception as e:
                debug_print(f"[APPS] launch {app.get('name')}: {e}")
        run_off_main_thread(work)

    def _remember(self, app, app_id):
        app["app_id"] = app_id
        self._mtime_after_save()
        return False

    def _mtime_after_save(self):
        # remember_app_id() saved apps.json: that is not a new choice of apps
        try:
            self._mtime = os.path.getmtime(apps_catalog.APPS_FILE)
        except OSError:
            pass
