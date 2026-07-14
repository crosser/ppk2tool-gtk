"""
GTK4 GUI for ppk2tool
"""

# python3-gi gir1.2-gtk-4.0 python3-ppk2tool

import os
import sys
from tty import setcbreak
import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Graphene, Pango

from ppk2tool import *


class PPK2Source(GLib.Source):
    def __init__(self, devpath, on_message):
        super().__init__()
        self.buffer = bytearray(1024)
        self.tty = open(
            devpath,
            "rb+",
            buffering=0,
            opener=lambda nm, flg: os.open(nm, flg | os.O_NOCTTY),
        )
        setcbreak(self.tty.fileno())
        self._fd_tag = self.add_unix_fd(self.tty.fileno(), GLib.IOCondition.IN)
        self.ctx = PPK2CTX().setcallback(on_message)
        print("PPK2Source inited from tty", self.tty)

    def send(self, cmd: PPK2Cmd, *args: int) -> None:
        print("PPK2Source send", cmd, args)
        self.tty.write(self.ctx.cmd(cmd, *args))

    # GSource virtual methods follow

    def prepare(self):
        return False, -1

    def check(self):
        return bool(self.query_unix_fd(self._fd_tag) & GLib.IOCondition.IN)

    def dispatch(self, _callback, _args):
        length = self.tty.readinto(self.buffer)
        # print("Read", length, "data", self.buffer[:length])
        self.ctx.inject(self.buffer[:length])
        return GLib.SOURCE_CONTINUE

    def close(self) -> None:
        self.destroy()
        self.tty.close()


class Graph(Gtk.Widget):
    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)

    def do_snapshot(self, s):
        colour = Gdk.RGBA()
        colour.parse("#000000")
        rect = Graphene.Rect().init(
            10, 10, self.get_width() - 20, self.get_height() - 20
        )
        s.append_color(colour, rect)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="PPK2Tool")

        kctrl = Gtk.EventControllerKey()
        kctrl.connect("key-pressed", self.on_keypress, None)
        self.add_controller(kctrl)

        self.set_default_size(640, 480)
        self.set_child(box := Gtk.Box(orientation=Gtk.Orientation.VERTICAL))
        box.append(button := Gtk.Button(label="Power"))
        button.connect("clicked", self.hello)
        box.append(graph := Graph())
        print("Added graph object", graph)

        devmon = Gio.File.new_for_path("/dev").monitor_directory(
            Gio.FileMonitorFlags.NONE
        )
        devmon.connect("changed", self.on_devchange, None)
        if self.findppk():
            print("PPK2 initialised")
        else:
            print("No PPK2")

    def findppk(self) -> bool:
        found = 0
        devname = None
        try:
            for e in os.listdir("/dev/serial/by-id"):
                if e.startswith("usb-Nordic_Semiconductor_PPK2"):
                    found += 1
                    devname = e
        except FileNotFoundError:
            pass
        if found != 1:
            print("zero or more than one profiler devices")
            self.ppk = None
            return False
        assert devname is not None, "listdir() returned entry None?!"
        devpath = os.path.join("/dev/serial/by-id", devname)
        print("Using PPK on", devpath)

        self.ppk = PPK2Source(devpath, self.on_ppk_result)
        print("Registered source", self.ppk)
        self.ppk.attach(GLib.MainContext.default())
        return true

    def on_devchange(
        self,
        fmon: Gio.FileMonitor,
        file: Gio.File,
        other: Gio.File,
        evtype: Gio.FileMonitorEvent,
        _: Literal[None],
    ):
        print("dev event", fmon, file, other, evtype)
        if self.findppk():
            print("PPK2 initialised")
        else:
            print("No PPK2")

    def on_keypress(
        self,
        _event: Gtk.Event,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
        _udata: Literal[None],
    ) -> None:
        if keyval == Gdk.KEY_q and state & Gdk.ModifierType.CONTROL_MASK:
            self.close()

    def hello(self, button):
        print("Clicked", button)
        if self.ppk:
            self.ppk.send(PPK2Cmd.GET_META_DATA)

    def on_ppk_result(self, cmd: PPK2Cmd, data: PPK2Meta | PPK2Sample) -> None:
        if isinstance(data, PPK2Meta):
            self.metadata = data
            print("metadata", self.metadata)
            self.vdd = self.metadata.VDD
        else:
            print(data)


class PPK2App(Adw.Application):

    def do_activate(self):
        MainWindow(self).present()


if __name__ == "__main__":
    app = PPK2App(application_id="org.average.ppk2tool")
    try:
        app.run()
    except KeyboardInterrupt:
        app.quit()
