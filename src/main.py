import kzserial
import sys
import serial
import kthread
import threading
import time
import inotify.adapters
import json
import collections
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt


class State:
    def __init__(self):
        self.listeners = collections.defaultdict(list)

    def attach_listener(self, property_name, callback):
        self.listeners[property_name].append(callback)

    def setter(self, property_name):
        return lambda value: self.__setattr__(property_name, value)

    def __setattr__(self, property_name, value):
        self.__dict__[property_name] = value
        for callback in self.listeners.get(property_name, []):
            callback(value)


class Filler(QLabel):
    """
    Filler class only containing a label
    To be removed when actual widgets are added
    """
    def __init__(self):
        super(Filler, self).__init__()
        self.setText("Some filler")


class GeneralConfigs(QWidget):
    """
    Top left quadrant of the window
    """
    def __init__(self):
        super(GeneralConfigs, self).__init__()

        # Add grid
        self.general_configs_grid = QGridLayout()
        self.setLayout(self.general_configs_grid)

        # Set up dropdown menu for ports
        # This will be updated from another thread
        self.ports_menu = QComboBox()
        self.ports_menu.setPlaceholderText("Select port")

        # Populate grid
        self.general_configs_grid.addWidget(self.ports_menu, 0, 0)


class KeyConfigs(QWidget):
    """
    Top right qudrant of the window
    """
    def __init__(self, state):
        super(KeyConfigs, self).__init__()

        # Set up dropdown menu for keys
        keys_menu = QComboBox()

        keys_menu.currentIndexChanged.connect(
            lambda value: state.setter('key_selected')(f"key_{value + 1}")
        )

        for i in range(9):
            keys_menu.addItem(f"key_{i+1}")

        # Add grid
        key_configs_grid = QGridLayout()
        key_configs_grid.addWidget(keys_menu, 0, 0)

        self.setLayout(key_configs_grid)


class Visualizer(QWidget):
    """
    Bottom right quadrant of the window
    """
    def __init__(self, state):
        super(Visualizer, self).__init__()

        # Sets up the progress bar
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setOrientation(Qt.Vertical)
        bar.setMaximum(400)
        bar.setMinimum(0)
        bar.setInvertedAppearance(True)
        state.attach_listener(
            'key_distance',
            lambda v: bar.setValue(round(v*100))
        )
        

        # Sets up switch icon
        switch_icon = QPixmap("../assets/switch.png")
        switch_label = QLabel()
        switch_label.setPixmap(switch_icon)

        # Populates grid
        grid = QGridLayout()
        grid.addWidget(bar, 0, 0)
        grid.addWidget(switch_label, 0, 1)

        self.setLayout(grid)


class MainWindow(QMainWindow):
    """
    Main aplication window
    """
    def __init__(self):
        super(MainWindow, self).__init__()
        state = State()
        self.state = state

        # Add a grid
        self.root_grid = QGridLayout()
        self.root_window = QWidget()
        self.root_window.setLayout(self.root_grid)
        self.setCentralWidget(self.root_window)

        # Create widgets
        self.key_configs = KeyConfigs(state)
        #self.key_configs.keys_menu.currentIndexChanged.connect(self.update_selected_key)
        self.general_configs = GeneralConfigs()
        self.general_configs.ports_menu.textActivated.connect(self.update_selected_port)
        self.visualizer = Visualizer(state)
        state.key_distance = 2.5

        # Populate grid
        self.root_grid.addWidget(self.general_configs, 0, 0)
        self.root_grid.addWidget(self.key_configs, 0, 1)
        self.root_grid.addWidget(self.visualizer, 1, 1)

        # Watch for changes in ports directory
        self.rpp = None
        self.watch_thread = kthread.KThread(target=self.watch_ports)
        self.watch_thread.start()

        # Get keys information
        self.info_thread = kthread.KThread(target=self.update_keys_info,
                                           args=([self.rpp]))

        # Set some defaults
        self.key_selected = "key_1"
        self.update_ports()


    def watch_ports(self):
        """
        Watches for changes in /dev/tty and
        updates ports if files for serial ports
        are created or deleted
        """
        watcher = inotify.adapters.Inotify()
        watcher.add_watch("/dev/")
        for event in watcher.event_gen(yield_nones=False):
            (_, event_types, path, filename) = event
            if "ttyA" in filename:
                if "IN_CLOSE_NOWRITE" in event_types or "IN_DELETE" in event_types:
                    self.update_ports()


    def update_ports(self):
        """
        Updates the port list
        """
        ports = kzserial.get_serial_ports()
        menu = self.general_configs.ports_menu
        menu.clear()
        if len(ports) > 0:
            menu.addItems(ports)
            if menu.currentIndex() == -1:
                # If list was previously empty
                # select first port automatically
                menu.setCurrentText(ports[0])
        else:
            menu.setCurrentIndex(-1)
        self.update_selected_port()


    def update_selected_port(self):
        """
        Updates selected port from dropdown menu
        """
        last_port = self.rpp
        self.port_selected = self.general_configs.ports_menu.currentText()
        try:
            self.rpp = serial.Serial(self.port_selected, timeout=0.5)
            if self.rpp != last_port:
                if self.info_thread.is_alive():
                    self.info_thread.terminate()
                self.info_thread = kthread.KThread(target=self.update_keys_info,
                                                       args=([self.rpp]))
                self.info_thread.start()
        except (OSError, serial.SerialException):
            self.rpp = None


    def update_keys_info(self, opened_port):
        """
        Updates the keys info dict from a serial port
        """
        while True:
            try:
                keys_info = kzserial.read_dict_from_port(opened_port)
                print(keys_info)
                key_distance = keys_info[self.state.key_selected]["distance"]
                self.visualizer.bar.setValue(round(key_distance*100))

            # Ignore json errors, they come from the pico 
            # sending some garbage through the serial port
            except json.decoder.JSONDecodeError:
                pass
            # If anything else happens, return from the thread
            except Exception:
                return


    def update_selected_key(self):
        """
        Updates selected key from dropdown menu
        """
        self.key_selected = self.key_configs.keys_menu.currentText()


    def closeEvent(self, a0: QCloseEvent):
        """
        Terminates threads and closes the main window
        """
        if self.info_thread.is_alive():
            self.info_thread.terminate()
            self.info_thread.join()
        if self.watch_thread.is_alive():
            self.watch_thread.terminate()
            self.watch_thread.join()
        return super().closeEvent(a0)


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
