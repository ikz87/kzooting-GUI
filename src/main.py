import kzserial
import sys
import serial
import time
import inotify.adapters
import json
import collections
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer


class State(QObject):
    """
    Implementation of the Observer Pattern to control application
    state in a centralized manner. Callbacks are always executed
    on the main thread of the application using Qt Signals.
    """

    __update_signal = pyqtSignal(str, object)

    def __init__(self):
        super(QObject, self).__init__()
        self.__dict__["listeners"] = collections.defaultdict(list)
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


class GeneralInfo(QWidget):
    """
    Top left quadrant of the window
    """

    def __init__(self, state):
        super(GeneralInfo, self).__init__()

        # Set up dropdown menu for ports
        ports_menu = QComboBox()
        ports_menu.textActivated.connect(state.setter("selected_port"))
        self.was_empty = True

        def update_ports(ports):
            ports_menu.clear()
            for port in ports:
                ports_menu.addItem(port)
            if self.was_empty and len(ports):
                ports_menu.setCurrentText(ports[0])
                state.selected_port = ports[0]
                self.was_empty = False
            elif len(ports) == 0:
                self.was_empty = True

        state.attach_listener("available_ports", update_ports)

        # Set up info strings
        info_strings = QLabel()
        info_strings.setText(
            "Internal temperature: 0°C"
        )

        state.attach_listener(
            "info", lambda info:
                info_strings.setText(
                    "Internal temperature: " + str(info["temperature"]) + "°C"))

        # Populate grid
        general_info_grid = QGridLayout()
        general_info_grid.addWidget(ports_menu, 0, 0, 1, 2)
        general_info_grid.addWidget(info_strings, 1, 1)
        self.setLayout(general_info_grid)


class GeneralConfigs(QWidget):
    """
    Bottom left quadrant of the window
    """
    def __init__(self, state):
        super(GeneralConfigs, self).__init__()
        self.state = state

        # Own copy of the configs dict
        state.attach_listener(
            "configs", lambda configs:
                update_options_from_dict(configs))

        # Add check boxes and input fields
        self.rapid_trigger_rb = QRadioButton("Rapid trigger")
        self.rapid_trigger_rb.setChecked(True)
        self.rapid_trigger_rb.toggled.connect(self.update_dict_from_options)
        self.fixed_actuation_rb = QRadioButton("Fixed actuation")

        actuation_method_vbox = QVBoxLayout()
        actuation_method_vbox.addWidget(self.rapid_trigger_rb)
        actuation_method_vbox.addWidget(self.fixed_actuation_rb)

        actuation_method = QGroupBox("Actuation method")
        actuation_method.clicked.connect(self.update_dict_from_options)
        actuation_method.setLayout(actuation_method_vbox)

        # Populate grid
        general_configs_grid = QGridLayout()
        general_configs_grid.addWidget(actuation_method, 0, 0)
        self.setLayout(general_configs_grid)

        def update_options_from_dict(configs):
            self.rapid_trigger_rb.setChecked(configs["general"]["rapid_trigger"])
            pass

    def update_dict_from_options(self):
        self.state.configs["general"]["rapid_trigger"] = self.rapid_trigger_rb.isChecked()
        pass



class KeyConfigs(QWidget):
    """
    Top right quadrant of the window
    """

    def __init__(self, state):
        super(KeyConfigs, self).__init__()

        # Set up dropdown menu for keys
        keys_menu = QComboBox()

        keys_menu.currentIndexChanged.connect(
            lambda value: state.setter("key_selected")(f"key_{value + 1}")
        )

        for i in range(9):
            keys_menu.addItem(f"key_{i+1}")

        # Populate grid
        key_configs_grid = QGridLayout()
        key_configs_grid.addWidget(keys_menu, 0, 0)
        key_configs_grid.addWidget(Filler(), 1, 0)
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
            "info",
            lambda info: bar.setValue(
                round(info[state.key_selected]["distance"] * 100)
            ),
        )

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
        general_info = GeneralInfo(state)
        general_configs = GeneralConfigs(state)
        key_configs = KeyConfigs(state)
        visualizer = Visualizer(state)
        save_button = QPushButton("&Save", self)
        save_button.clicked.connect(self.send_configs_to_pico)

        # Populate grid
        self.root_grid.addWidget(general_info, 0, 0)
        self.root_grid.addWidget(general_configs, 1, 0)
        self.root_grid.addWidget(key_configs, 0, 1)
        self.root_grid.addWidget(visualizer, 1, 1)
        self.root_grid.addWidget(save_button, 2, 0, 1, 2)

        # Watch for changes in ports directory
        self.rpp = None

        watcher = inotify.adapters.Inotify(block_duration_s=0.01)
        watcher.add_watch("/dev/")

        def watch_ports():
            """
            Watches for changes in /dev/tty and
            updates ports accordingly
            """
            for event in watcher.event_gen(yield_nones=False, timeout_s=0.01):
                (_, event_types, path, filename) = event
                if "ttyA" in filename:
                    if "IN_CLOSE_NOWRITE" in event_types or "IN_DELETE" in event_types:
                        self.state.available_ports = kzserial.get_serial_ports()

        state.attach_listener(
            "selected_port", lambda port: self.update_open_port(port)
        )

        self.state.available_ports = kzserial.get_serial_ports()
        timer1 = QTimer(self)
        timer1.timeout.connect(watch_ports)
        timer1.start(500)

        timer2 = QTimer(self)
        timer2.timeout.connect(self.get_info_from_pico)
        timer2.start(10)

    def send_configs_to_pico(self):
        """
        Sends a configs to the pico to be rewritten
        """
        try:
            configs_dict = self.state.configs
            configs_json = json.dumps(configs_dict)
            print("sending" +configs_json)
            self.rpp.write((configs_json + "\n").encode())
            print("done")
        except:
            pass

    def update_open_port(self, port):
        """
        Opens a new port and closes the last one
        """
        try:
            if self.rpp != None:
                self.rpp.close()
            self.rpp = serial.Serial(port, timeout=0.1)
            response = kzserial.get_response_from_request(self.rpp, "configs_request")
            self.state.configs = response
        except (OSError, serial.SerialException, json.JSONDecodeError) as e:
            self.rpp = None

    def get_info_from_pico(self):
        """
        Updates general information
        """
        try:
            if self.rpp != None:
                response = kzserial.get_response_from_request(self.rpp, "info_request")
                self.state.info = response
        except (OSError, serial.SerialException, json.JSONDecodeError) as e:
            pass

    def closeEvent(self, a0: QCloseEvent):
        return super().closeEvent(a0)


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
