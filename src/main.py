import gi
import sys
from threading import Thread
import kzserial

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk


class ScaleWin(Gtk.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scale_min = 0
        scale_max = 4
        scale_step = 0.1
        scale_orientation = 1
        self.scale = Gtk.Scale.new_with_range(scale_orientation,
                                              scale_min,
                                              scale_max,
                                              scale_step)
        self.scale.set_value(2)
        self.rpp = kzserial.get_serial_port()
        self.rpp.readline()
        info_thread = Thread(target=self.update_value, args=())
        info_thread.start()
        #self.scale.set_sensitive(False)
        self.add(self.scale)
        self.show_all()

    def update_value(self):
        while True:
                keys_info = kzserial.read_dict_from_port(self.rpp)
                key_value = keys_info["key_8"]["distance"]
                if key_value != self.scale.get_value():
                    self.scale.set_value(keys_info["key_8"]["distance"])
                    self.show_all()
                print(keys_info)


class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.kzooting.gui")

    def do_startup(self):
        Gtk.Application.do_startup(self)

    def do_activate(self):
        self.window = ScaleWin(title="key viewer",
                               application=self)
        self.window.present()


def main():
    kzooting_app = MyApp()
    kzooting_app.run(sys.argv)
    pass


if __name__ == "__main__":
    main()
