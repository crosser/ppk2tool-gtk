"""
GTK4 GUI for ppk2tool
"""

# python3-gi gir1.2-gtk-4.0 python3-ppk2tool

import sys
import gi  # type: ignore [import-untyped]

gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk  # type: ignore [import-untyped]

from .gui import MainWindow


class PPK2App(Adw.Application):  # type: ignore [misc]
    """GTK4 Application"""

    def do_activate(self) -> None:
        MainWindow(self).present()


Gtk.init()


def main() -> None:
    """
    Main entry point, for the benefit of pyproject's "scripts" idiosyncrasy
    """

    app = PPK2App(application_id="org.average.ppk2tool")
    try:
        app.run(sys.argv)
    except KeyboardInterrupt:
        app.quit()


if __name__ == "__main__":
    main()
