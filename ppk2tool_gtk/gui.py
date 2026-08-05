"""
GTK4 GUI for ppk2tool: window and widgets
"""

from collections import deque
import os
from typing import Any, Callable, Literal

from dbus import SystemBus, String  # type: ignore [import-untyped]
from dbus.mainloop.glib import DBusGMainLoop  # type: ignore [import-untyped]
from tty import setcbreak
import gi  # type: ignore [import-untyped]

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import (  # type: ignore [import-untyped]
    Adw,
    Gdk,
    Gio,
    GLib,
    Gtk,
)

from ppk2tool import *
from .graph import Graph


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
        on_message: Callable[
            [PPK2Cmd, PPK2Meta | PPK2Sample | PPK2Stats], None
        ],
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
        self.devpath = devpath
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


class MainWindow(Gtk.ApplicationWindow):  # type: ignore [misc]
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="PPK2Tool")

        self.vdd: float = 3.7
        self.passthrough: bool = False
        self.hist: deque[tuple[float, float, float]] = deque(maxlen=1000)
        self.min = 1.0
        self.max = 0.00001
        self.avg = 0.00001
        self.count = 0
        self.amps = 0.0
        self.ampcount = 0
        self.ppk: None | PPK2Source = None
        GLib.timeout_add(10, self.periodic, None)

        kctrl = Gtk.EventControllerKey()
        kctrl.connect("key-pressed", self.on_keypress, None)
        self.add_controller(kctrl)

        self.set_titlebar(titlebar := Gtk.HeaderBar())
        titlebar.pack_start(about_button := Gtk.Button(label="About"))
        about_button.set_icon_name("help-about-symbolic")
        about_button.connect("clicked", self.show_about)

        self.set_child(box := Gtk.Box(orientation=Gtk.Orientation.VERTICAL))

        box.append(topbox := Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL))
        spacepad(topbox)
        topbox.set_spacing(5)
        topbox.append(Gtk.Label(label="Power:"))
        topbox.append(pwrbutton := Gtk.ToggleButton(label="\u23FB"))
        pwrbutton.set_valign(Gtk.Align.CENTER)
        pwrbutton.set_active(False)
        pwrbutton.connect("clicked", self.on_pwrchange)
        topbox.append(Gtk.Label(label="Measure:"))
        topbox.append(measurebtn := Gtk.ToggleButton(label="🗠"))
        measurebtn.set_valign(Gtk.Align.CENTER)
        measurebtn.set_active(False)
        measurebtn.connect("clicked", self.on_measurechange)
        topbox.append(Gtk.Label(label="Voltage:"))
        self.voltage = Gtk.SpinButton(orientation=Gtk.Orientation.HORIZONTAL)
        topbox.append(self.voltage)
        self.voltage.props.adjustment = Gtk.Adjustment(
            lower=0.8, upper=5.0, step_increment=0.01, page_increment=0.2
        )
        self.voltage.props.digits = 2
        self.voltage.set_numeric(True)
        self.voltage.set_value(self.vdd)
        self.voltage.connect("value-changed", self.on_voltage)
        topbox.append(Gtk.Label(label="Current (mA):"))
        self.current = Gtk.Label()
        self.current.set_text("  0.000")
        topbox.append(self.current)

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

        SystemBus(mainloop=DBusGMainLoop()).add_signal_receiver(
            self.on_devchange, member_keyword="UnitNew"
        )
        self.findppk()

    def show_about(self, button) -> None:
        # print("About button pressed")
        dialog = Adw.AboutWindow(transient_for=self)
        dialog.set_application_name("Power Profiler 2 Measurement Tool")
        dialog.set_version("?.?")
        dialog.set_developer_name("Eugene Crosser")
        dialog.set_license_type(Gtk.License(Gtk.License.MIT_X11))
        dialog.set_comments("GUI for Nordic Semiconductor Power Profiler 2")
        dialog.set_website("https://git.average.org/cgit/ppk2tool-gtk.git")
        # dialog.set_issue_url("https://github.com/")
        # dialog.add_credit_section("Contributors", ["Name1 url"])
        # dialog.set_translator_credits("Name1 url")
        dialog.set_copyright("© 2026 Eugene Crosser")
        # dialog.set_developers(["Eugene Crosser"])
        # icon must be uploaded in ~/.local/share/icons or /usr/share/icons
        # dialog.set_application_icon("org.average.ppk2tool-gtk")
        dialog.set_visible(True)

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
        if self.ppk:
            if self.ppk.devpath == devpath:
                print(
                    "ignoring devchange event for an already open ppk", devpath
                )
                return
            else:
                print("new device, closing the old one")
                self.ppk.close()

        self.ppk = PPK2Source(devpath, self.on_ppk_result)
        self.ppk.attach(GLib.MainContext.default())
        self.ppk.send(
            PPK2Cmd.REGULATOR_SET, *divmod(int(self.vdd * 1000.0), 256)
        )
        self.ppk.send(PPK2Cmd.SET_POWER_MODE, 1 if self.passthrough else 2)
        self.ppk.send(PPK2Cmd.GET_META_DATA)
        self.bottom.set_text(devpath[devpath.rfind("/") + 1 :])

    def on_devchange(self, *args: Any, UnitNew: None | str) -> None:
        if (
            UnitNew in ("UnitNew", "UnitRemoved")
            and "Nordic_Semiconductor_PPK2" in args[0]
        ):
            # print("dev event", args, UnitNew)
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

    def on_pwrchange(self, button: Gtk.ToggleButton) -> None:
        state = button.get_active()
        print("power", "on" if state else "off")
        if self.ppk:
            self.ppk.send(PPK2Cmd.DEVICE_RUNNING_SET, int(state))

    def on_measurechange(self, button: Gtk.ToggleButton) -> None:
        state = button.get_active()
        print("measuring" if state else "stopped")
        if self.ppk:
            self.ppk.send(
                PPK2Cmd.AVERAGE_START if state else PPK2Cmd.AVERAGE_STOP
            )

    def on_voltage(self, sbtn: Gtk.Widget) -> None:
        self.vdd = sbtn.get_value()
        if self.ppk:
            self.ppk.send(
                PPK2Cmd.REGULATOR_SET, *divmod(int(self.vdd * 1000.0), 256)
            )


    def on_ppk_result(
        self, cmd: PPK2Cmd, data: PPK2Meta | PPK2Sample | PPK2Stats
    ) -> None:
        if isinstance(data, PPK2Meta):
            self.metadata = data
            print("metadata", self.metadata)
            self.vdd = self.metadata.VDD / 1000.0
            self.voltage.set_value(self.vdd)
        elif isinstance(data, PPK2Sample):
            # print(data)
            if data.amps > self.max:
                self.max = data.amps
            if data.amps < self.min:
                self.min = data.amps
            self.avg = self.avg * 0.8 + data.amps * 0.2
            self.count += 1
        elif isinstance(data, PPK2Stats):
            pass
        else:
            print("Unhandled data:", data)

    def periodic(self, _: Any) -> Literal[True]:
        # print("Periodic called after", self.count, "samples")
        if self.count:
            self.hist.append((self.min, self.avg, self.max))
            self.min = 1.0
            self.max = 0.00001
            # self.avg = 0.00001
            self.count = 0
            self.amps = self.avg * 0.1 + self.amps * 0.9
            self.ampcount += 1
            if self.ampcount >= 50:
                self.current.set_text(f"{(self.amps * 1000.0):8.3f}")
                self.ampcount = 0
            self.graph.queue_draw()
        return True
