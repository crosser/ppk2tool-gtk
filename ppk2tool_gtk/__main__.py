"""
GTK4 GUI for ppk2tool
"""

# python3-gi gir1.2-gtk-4.0 python3-ppk2tool

from collections import deque
from math import log10
import os
import sys
from typing import Any, Callable, Literal

from dbus import SessionBus, String  # type: ignore [import-untyped]
from dbus.mainloop.glib import DBusGMainLoop  # type: ignore [import-untyped]
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

Gtk.init()


def spacepad(what: Gtk.Widget) -> None:
    what.set_spacing(5)
    what.set_margin_top(5)
    what.set_margin_bottom(5)
    what.set_margin_start(5)
    what.set_margin_end(5)


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
        # print("PPK2Source inited from tty", self.tty)

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


class MainWindow(Gtk.ApplicationWindow):  # type: ignore [misc]
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="PPK2Tool")

        self.voltage: float = 3.7
        self.passthrough: bool = False
        self.hist: deque[tuple[float, float, float]] = deque(maxlen=1000)
        self.min = 1.0
        self.max = 0.00001
        self.avg = 0.00001
        self.count = 0
        self.ppk: None | PPK2Source = None
        GLib.timeout_add(10, self.periodic, None)

        kctrl = Gtk.EventControllerKey()
        kctrl.connect("key-pressed", self.on_keypress, None)
        self.add_controller(kctrl)

        self.set_child(box := Gtk.Box(orientation=Gtk.Orientation.VERTICAL))

        box.append(topbox := Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL))
        spacepad(topbox)
        topbox.set_spacing(5)
        topbox.append(pwrswitch := Gtk.Switch())
        pwrswitch.set_active(False)
        pwrswitch.connect("state-set", self.on_pwrchange)
        topbox.append(Gtk.Label(label="Power"))
        topbox.append(measureswitch := Gtk.Switch())
        measureswitch.set_active(False)
        measureswitch.connect("state-set", self.on_measurechange)
        topbox.append(Gtk.Label(label="Measure"))

        box.append(midbox := Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL))
        spacepad(midbox)
        self.graph = Graph(self.hist)
        midbox.append(self.graph)

        box.append(
            bottombox := Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        )
        spacepad(bottombox)
        self.bottom = Gtk.Label(label="No PPK2 Connected")
        bottombox.append(self.bottom)

        SessionBus(mainloop=DBusGMainLoop()).add_signal_receiver(
            self.on_devchange, member_keyword="UnitNew"
        )
        self.findppk()

    def findppk(self) -> None:
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
            if self.ppk:
                self.ppk.close()
            self.ppk = None
            self.bottom.set_text("zero or more than one profiler devices")
            return

        assert devname is not None, "listdir() returned entry None?!"
        devpath = os.path.join("/dev/serial/by-id", devname)

        self.ppk = PPK2Source(devpath, self.on_ppk_result)
        self.ppk.attach(GLib.MainContext.default())
        self.ppk.send(
            PPK2Cmd.REGULATOR_SET, *divmod(int(self.voltage * 1000.0), 256)
        )
        self.ppk.send(PPK2Cmd.SET_POWER_MODE, 1 if self.passthrough else 2)
        self.ppk.send(PPK2Cmd.GET_META_DATA)
        self.bottom.set_text(devpath[devpath.rfind("/") + 1 :])

    def on_devchange(self, *args: Any, UnitNew: None | str) -> None:
        if (
            args
            and isinstance(args[0], String)
            and "Nordic_Semiconductor_PPK2" in args[0]
        ):
            # print("dev event", UnitNew)
            self.findppk()

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

    def on_pwrchange(self, switch: Gtk.Widget, state: bool) -> None:
        print("power", "on" if state else "off")
        if self.ppk:
            self.ppk.send(PPK2Cmd.DEVICE_RUNNING_SET, int(state))

    def on_measurechange(self, switch: Gtk.Widget, state: bool) -> None:
        print("measuring" if state else "stopped")
        if self.ppk:
            self.ppk.send(
                PPK2Cmd.AVERAGE_START if state else PPK2Cmd.AVERAGE_STOP
            )

    def on_ppk_result(self, cmd: PPK2Cmd, data: PPK2Meta | PPK2Sample) -> None:
        if isinstance(data, PPK2Meta):
            self.metadata = data
            print("metadata", self.metadata)
            self.vdd = self.metadata.VDD
        else:
            # print(data)
            amps = data.amps
            if amps < 0.00001:
                amps = 0.00001
            elif amps > 1.0:
                amps = 1.0
            if amps > self.max:
                self.max = amps
            if amps < self.min:
                self.min = amps
            self.avg = self.avg * 0.99 + amps * 0.01
            self.count += 1

    def periodic(self, _: Any) -> Literal[True]:
        # print("Periodic called after", self.count, "samples")
        if self.count:
            self.hist.append((self.min, self.avg, self.max))
            self.min = 1.0
            self.max = 0.00001
            # self.avg = 0.00001
            self.count = 0
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
