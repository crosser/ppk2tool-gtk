"""
GTK4 GUI for ppk2tool
"""

# python3-gi gir1.2-gtk-4.0 python3-ppk2tool

from collections import deque
from math import log10
import os
import sys
from typing import Any, Callable, Literal

from tty import setcbreak
import gi  # type: ignore [import-untyped]

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import (  # type: ignore [import-untyped]
    Adw,
    Gdk,
    Gio,
    GLib,
    Gtk,
    Graphene,
    Pango,
)

from ppk2tool import *

D_WIDTH = 1200
D_HEIGHT = 800

LABELS = {
    1: "10μA",
    10: "100μA",
    100: "1mA",
    1000: "10mA",
    10000: "100mA",
    100000: "1A",
}


class PPK2Source(GLib.Source):  # type: ignore [misc]
    def __init__(
        self,
        devpath: str,
        on_message: Callable[[PPK2Cmd, PPK2Meta | PPK2Sample], None],
    ) -> None:
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

    def prepare(self) -> tuple[bool, int]:
        return False, -1

    def check(self) -> bool:
        return bool(self.query_unix_fd(self._fd_tag) & GLib.IOCondition.IN)

    def dispatch(self, _callback: Any, _args: Any) -> Any:  # actually -> bool
        length = self.tty.readinto(self.buffer)
        # print("Read", length, "data", self.buffer[:length])
        self.ctx.inject(self.buffer[:length])
        return GLib.SOURCE_CONTINUE

    def close(self) -> None:
        self.destroy()
        self.tty.close()


class Graph(Gtk.Widget):  # type: ignore [misc]
    def __init__(self, hist: deque[tuple[float, float, float]]) -> None:
        super().__init__()
        self.hist = hist
        # self.set_hexpand(True)
        # self.set_vexpand(True)
        self.set_size_request(D_WIDTH, D_HEIGHT)

    def do_snapshot(self, s: Graphene.Snapshot) -> None:
        w = self.get_width()
        h = self.get_height()
        colour = Gdk.RGBA()
        colour.parse("#000000")
        rect = Graphene.Rect().init(0, 0, w, h)
        s.append_color(colour, rect)
        x0 = 65
        y0 = 10
        w = w - x0 - 10
        h = h - y0 - 30

        for i, (mn, av, mx) in enumerate(self.hist):
            # print("Values", i, mn, av, mx)
            x = x0 + i * w // 1000
            colour.parse("#00ff00")
            y1 = log10(mx * 100000.0) * h // 5
            y2 = log10(mn * 100000.0) * h // 5
            # print("y1", y1, "y2", y2)
            s.append_color(
                colour, Graphene.Rect().init(x, h + y0 - y1, 1, y1 - y2)
            )
            colour.parse("#ff0000")
            y = log10(av * 100000.0) * h // 5
            s.append_color(
                colour, Graphene.Rect().init(x, h + y0 - y - 2, 1, 4)
            )

        font = Pango.FontDescription.new()
        font.set_family("Sans")
        font.set_size(12 * Pango.SCALE)
        layout = Pango.Layout.new(self.get_pango_context())
        layout.set_font_description(font)
        point = Graphene.Point()
        band = 1
        for i in range(1, 100001):  # 10 uA to 1 A
            if i >= band * 10:
                band *= 10
            if i // band and not i % band:
                y = log10(i) * h // 5
                # print("band =", band, "i =", i, "y =", y)
                if i == band:
                    colour.parse("#ffffff")
                    layout.set_text(LABELS[band])
                    point.x = x0 - 55
                    point.y = h + y0 - y - 10
                    s.save()
                    s.translate(point)
                    s.append_layout(layout, colour)
                    s.restore()
                else:
                    colour.parse("#808080")
                s.append_color(
                    colour, Graphene.Rect().init(x0, h + y0 - y, w, 1)
                )
        colour.parse("#ffffff")
        for i in range(11):
            layout.set_text(str(i))
            x = x0 + i * w // 10
            point.x = x - 5
            point.y = h + y0
            s.save()
            s.translate(point)
            s.append_layout(layout, colour)
            s.restore()
            s.append_color(colour, Graphene.Rect().init(x, y0, 1, h))
        # colour.parse("#00ff00")
        # for i in range(100000):
        #     y = log10(i + 1) * h // 5
        #     s.append_color(
        #         colour,
        #         Graphene.Rect().init(x0 + i * w // 100000, h + y0 - y, 1, 1),
        #     )


class MainWindow(Gtk.ApplicationWindow):  # type: ignore [misc]
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="PPK2Tool")

        self.hist: deque[tuple[float, float, float]] = deque(maxlen=1000)
        GLib.timeout_add(10, self.periodic, None)

        kctrl = Gtk.EventControllerKey()
        kctrl.connect("key-pressed", self.on_keypress, None)
        self.add_controller(kctrl)

        self.set_child(box := Gtk.Box(orientation=Gtk.Orientation.VERTICAL))
        box.append(button := Gtk.Button(label="Power"))
        button.connect("clicked", self.hello)
        self.graph = Graph(self.hist)
        box.append(self.graph)

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
        return True

    def on_devchange(
        self,
        fmon: Gio.FileMonitor,
        file: Gio.File,
        other: Gio.File,
        evtype: Gio.FileMonitorEvent,
        _: Literal[None],
    ) -> None:
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

    def hello(self, button: Gtk.Widget) -> None:
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

    def periodic(self, _: Any) -> Literal[True]:
        # print("Periodic called")
        self.hist.append((0.001, 0.01, 0.1))
        self.graph.queue_draw()
        return True


class PPK2App(Adw.Application):  # type: ignore [misc]

    def do_activate(self) -> None:
        MainWindow(self).present()


if __name__ == "__main__":
    app = PPK2App(application_id="org.average.ppk2tool")
    try:
        app.run()
    except KeyboardInterrupt:
        app.quit()
