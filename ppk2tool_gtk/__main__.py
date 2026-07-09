import sys
import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gtk, Adw, Graphene, Pango


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("PPK2Tool")
        self.set_default_size(640, 480)
        self.set_child(box := Gtk.Box(orientation=Gtk.Orientation.VERTICAL))
        box.append(button := Gtk.Button(label="Power"))
        button.connect("clicked", self.hello)
        box.append(graph := Graph())
        print("Added graph object", graph)

    def hello(self, button):
        print("Clicked", button)


class PPK2App(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(application=app)
        self.win.present()


if __name__ == "__main__":
    app = PPK2App(application_id="org.average.ppk2tool")
    app.run()
