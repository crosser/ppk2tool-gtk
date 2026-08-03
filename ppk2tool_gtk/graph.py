"""
GTK4 GUI for ppk2tool
"""

from collections import deque
from math import log10
from typing import Any, Callable, Literal

from dbus import SystemBus, String  # type: ignore [import-untyped]
from dbus.mainloop.glib import DBusGMainLoop  # type: ignore [import-untyped]
from tty import setcbreak
import gi  # type: ignore [import-untyped]

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import (  # type: ignore [import-untyped]
    Gdk,
    Gtk,
    Graphene,
    Pango,
)

from ppk2tool import *

D_WIDTH = 800
D_HEIGHT = 400

LABELS = {
    1: "10μA",
    10: "100μA",
    100: "1mA",
    1000: "10mA",
    10000: "100mA",
    100000: "1A",
}


def spacepad(what: Gtk.Widget) -> None:
    what.set_spacing(5)
    what.set_margin_top(5)
    what.set_margin_bottom(5)
    what.set_margin_start(5)
    what.set_margin_end(5)


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
