import kzserial
import sys
import serial
import kthread
import threading
import time
import inotify.adapters
import json
import collections
import queue
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal, QObject


class State(QObject):
    """
    Implementation of the Observer Pattern to control application
    state in a centralized manner. Callbacks are always executed
    on the main thread of the application using Qt Signals.
    """
    __update_signal = pyqtSignal(str, object)
    def __init__(self):
        super(QObject, self).__init__()
        self.listeners = collections.defaultdict(list)
        self.__update_signal.connect(self.__execute_callbacks)

    def attach_listener(self, property_name, callback):
        self.listeners[property_name].append(callback)

    def setter(self, property_name):
        return lambda value: self.__setattr__(property_name, value)

    def __execute_callbacks(self, property_name, value):
        for callback in self.listeners.get(property_name, []):
            callback(value)

    def __setattr__(self, property_name, value):
        self.__dict__[property_name] = value
        self.__update_signal.emit(property_name, value)


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
    def __init__(self, state):
        super(GeneralConfigs, self).__init__()

        # Set up dropdown menu for ports
        ports_menu = QComboBox()
        ports_menu.setPlaceholderText("Select port")
        ports_menu.textActivated.connect(state.setter('selected_port'))
        self.was_empty = True

        def update_ports(ports):
            ports_menu.clear()
            for port in ports:
                ports_menu.addItem(port)
            if self.was_empty and len(ports):
                ports_menu.setCurrentText(ports[0])
                state.selected_port = ports[0]
                self.was_empty = False
            else:
                self.was_empty = True

        state.attach_listener("available_ports", update_ports)

        # Populate grid
        general_configs_grid = QGridLayout()
        general_configs_grid.addWidget(ports_menu, 0, 0)

        self.setLayout(general_configs_grid)


class KeyConfigs(QWidget):
    """
    Top right quadrant of the window
    """
    def __init__(self, state):
        super(KeyConfigs, self).__init__()

        # Set up dropdown menu for keys
        keys_menu = QComboBox()

        keys_menu.currentIndexChanged.connect(
            lambda value: state.setter('key_selected')(f"key_{value + 1}"))

        for i in range(9):
            keys_menu.addItem(f"key_{i+1}")

        # Populate grid
        key_configs_grid = QGridLayout()
        key_configs_grid.addWidget(keys_menu, 0, 0)

        self.setLayout(key_configs_grid)


class Visualizer(QWidget):
    """
    Bottom right quadrant of the window
    """
    def __init__(self, state):
        super(Visualizer, self).__init__()

        # Set up the progress bar
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setOrientation(Qt.Vertical)
        bar.setMaximum(400)
        bar.setMinimum(0)
        bar.setInvertedAppearance(True)
        state.attach_listener(
            'key_distance',
            lambda value: bar.setValue(round(value*100)))

        # Set up switch icon
        switch_icon = QPixmap("../assets/switch.png")
        switch_label = QLabel()
        switch_label.setPixmap(switch_icon)

        # Populate grid
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
        key_configs = KeyConfigs(state)
        general_configs = GeneralConfigs(state)
        visualizer = Visualizer(state)

        # Populate grid
        self.root_grid.addWidget(general_configs, 0, 0)
        self.root_grid.addWidget(key_configs, 0, 1)
        self.root_grid.addWidget(visualizer, 1, 1)

        # Watch for changes in ports directory
        self.rpp = None
        self.watch_thread = kthread.KThread(target=self.watch_ports)
        self.watch_thread.start()

        state.attach_listener(
            'selected_port',
            lambda port: self.update_selected_port(port))

        # Get keys information
        self.info_thread = kthread.KThread(target=self.update_pico_info,
                                           args=([self.rpp]))

    def watch_ports(self):
        """
        Watches for changes in /dev/tty and
        updates ports accordingly
        """
        self.state.available_ports = kzserial.get_serial_ports()
        watcher = inotify.adapters.Inotify()
        watcher.add_watch("/dev/")
        for event in watcher.event_gen(yield_nones=False):
            (_, event_types, path, filename) = event
            if "ttyA" in filename:
                if "IN_CLOSE_NOWRITE" in event_types or "IN_DELETE" in event_types:
                    self.state.available_ports = kzserial.get_serial_ports()

    def update_selected_port(self, port):
        """
        Updates selected port from dropdown menu
        """
        try:
            if self.info_thread.is_alive():
                self.info_thread.terminate()
            if self.rpp != None:
                self.rpp.close()
            self.rpp = serial.Serial(port, timeout=0.5)
            self.info_thread = kthread.KThread(target=self.update_pico_info,
                                               args=([self.rpp]))
            self.info_thread.start()
        except (OSError, serial.SerialException):
            self.rpp = None

    def update_pico_info(self, port):
        """
        Updates the keys info dict from a serial port
        """
        while True:
            try:
                pico_info = kzserial.get_response_from_request(port, "info_request")
                self.state.key_distance = pico_info[self.state.key_selected]["distance"]

            # Ignore json errors, they come from the pico 
            # sending some garbage through the serial port
            except json.decoder.JSONDecodeError:
                pass
            # If anything else happens, return from the thread
            except Exception as e:
                print(e)

                return

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
