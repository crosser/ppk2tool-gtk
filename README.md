# GUI to operate Nordic Semiconductor Power Profiler Kit 2

This is a GTK4 based UI to visualize measurements coming from
Nordic Semiconductor's
[Power Profiler Kit 2](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2)

![Screenshot](PPK2Tool-screenshot.png)

It's written in Python, but relies on Linux way to detect USB-Serial devices,
so it is only usable on Linux. This repository / package is the GUI part
only, and relies on a separate Python module, `ppk2tool`, for communication
with the device.

In its present form, the tool relies on Linux specific way to get notified
about connection and disconnection of USB devices, and Linux specific way
of discovering the desired type of device. Contributions of code that would
make it usable on other platforms are welcome (but no AI produced, please!).

Home repo:
[https://git.average.org/cgit/ppk2tool-gtk.git/](https://git.average.org/cgit/ppk2tool-gtk.git/)
or
[github mirror](https://github.com/crosser/ppk2tool-gtk)

Uses low level library:
[https://git.average.org/cgit/ppk2tool.git/](https://git.average.org/cgit/ppk2tool.git/)
or
[github mirror](https://github.com/crosser/ppk2tool)
