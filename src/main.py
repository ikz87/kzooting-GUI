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
            "Internal temperature: 0.00°C\n"
            "Reports per second: 000 (0.00ms)\n"
        )

        state.attach_listener(
            "info", lambda info:
                info_strings.setText(
                    f"Internal temperature: {info['temperature']:.1f}°C\n"
                    f"Reports per second: {1000/info['report_time']:.0f} ({info['report_time']:.2f}ms)"))

        # Populate grid
        general_info_grid = QGridLayout()
        general_info_grid.addWidget(ports_menu, 0, 0)
        general_info_grid.addWidget(info_strings, 1, 0)
        self.setLayout(general_info_grid)


class GeneralConfigs(QWidget):
    """
    Bottom left quadrant of the window
    """
    def __init__(self, state):
        super(GeneralConfigs, self).__init__()
        self.state = state
        state.out_configs["general"] = {}

        # Add check boxes and input fields
        rapid_trigger_rb = QRadioButton("Rapid trigger")
        rapid_trigger_rb.setChecked(True)
        fixed_actuation_rb = QRadioButton("Fixed actuation")

        actuation_method_vbox = QVBoxLayout()
        actuation_method_vbox.addWidget(rapid_trigger_rb)
        actuation_method_vbox.addWidget(fixed_actuation_rb)
        actuation_method_vbox.addStretch()

        actuation_method = QGroupBox("Actuation method")
        actuation_method.setLayout(actuation_method_vbox)

        # Rapid trigger specific options
        sensitivity = QDoubleSpinBox()
        sensitivity.setSuffix("mm")
        sensitivity.setDecimals(2)
        sensitivity.setRange(0.1, 1)
        sensitivity.setSingleStep(0.05)
        sensitivity_label = QLabel()
        sensitivity_label.setText("Sensitivity")
        sensitivity_label.setBuddy(sensitivity)

        top_deadzone = QDoubleSpinBox()
        top_deadzone.setSuffix("mm")
        top_deadzone.setDecimals(2)
        top_deadzone.setRange(0.1, 1)
        top_deadzone.setSingleStep(0.05)
        top_deadzone_label = QLabel()
        top_deadzone_label.setText("Top deadzone")
        top_deadzone_label.setBuddy(top_deadzone)

        bottom_deadzone = QDoubleSpinBox()
        bottom_deadzone.setSuffix("mm")
        bottom_deadzone.setDecimals(2)
        bottom_deadzone.setRange(0.1, 1)
        bottom_deadzone.setSingleStep(0.05)
        bottom_deadzone_label = QLabel()
        bottom_deadzone_label.setText("Bottom deadzone")
        bottom_deadzone_label.setBuddy(bottom_deadzone)

        rt_options_vbox = QVBoxLayout()
        rt_options_vbox.addWidget(sensitivity_label)
        rt_options_vbox.addWidget(sensitivity)
        rt_options_vbox.addWidget(top_deadzone_label)
        rt_options_vbox.addWidget(top_deadzone)
        rt_options_vbox.addWidget(bottom_deadzone_label)
        rt_options_vbox.addWidget(bottom_deadzone)
        rt_options_vbox.addStretch()

        rt_options = QGroupBox("Rapid trigger options")
        rt_options.setLayout(rt_options_vbox)

        # Fixed actuation scpecific options
        actuation_point = QDoubleSpinBox()
        actuation_point.setSuffix("mm")
        actuation_point.setDecimals(2)
        actuation_point.setRange(0.3, 3.5)
        actuation_point.setSingleStep(0.05)
        actuation_point_label = QLabel()
        actuation_point_label.setText("Actuation point")
        actuation_point_label.setBuddy(actuation_point)

        actuation_reset = QDoubleSpinBox()
        actuation_reset.setSuffix("mm")
        actuation_reset.setDecimals(2)
        actuation_reset.setRange(0.1, 1)
        actuation_reset.setSingleStep(0.05)
        actuation_reset_label = QLabel()
        actuation_reset_label.setText("Actuation reset")
        actuation_reset_label.setBuddy(actuation_reset)

        fa_options_vbox = QVBoxLayout()
        fa_options_vbox.addWidget(actuation_point_label)
        fa_options_vbox.addWidget(actuation_point)
        fa_options_vbox.addWidget(actuation_reset_label)
        fa_options_vbox.addWidget(actuation_reset)

        fa_options = QGroupBox("Fixed actuation options")
        fa_options.setLayout(fa_options_vbox)
        fa_options_vbox.addStretch()

        # Populate grid
        sub_options = QStackedWidget()
        sub_options.addWidget(rt_options)
        sub_options.addWidget(fa_options)

        general_configs_grid = QGridLayout()
        general_configs_grid.addWidget(actuation_method, 0, 0)
        general_configs_grid.addWidget(sub_options, 1, 0)
        self.setLayout(general_configs_grid)

        def update_options_from_dict(configs):
            sensitivity.setValue(configs["general"]["sensitivity"])
            top_deadzone.setValue(configs["general"]["top_deadzone"])
            bottom_deadzone.setValue(configs["general"]["bottom_deadzone"])
            actuation_point.setValue(configs["general"]["actuation_point"])
            actuation_reset.setValue(configs["general"]["actuation_reset"])

            # Update group box that is shown
            if configs["general"]["rapid_trigger"]:
                rapid_trigger_rb.setChecked(True)
                sub_options.setCurrentWidget(rt_options)
            else:
                fixed_actuation_rb.setChecked(True)
                sub_options.setCurrentWidget(fa_options)

        def update_dict_from_options(_configs):
            state.out_configs["general"]["rapid_trigger"] = rapid_trigger_rb.isChecked()
            state.out_configs["general"]["sensitivity"] = sensitivity.value()
            state.out_configs["general"]["top_deadzone"] = top_deadzone.value()
            state.out_configs["general"]["bottom_deadzone"] = bottom_deadzone.value()
            state.out_configs["general"]["actuation_point"] = actuation_point.value()
            state.out_configs["general"]["actuation_reset"] = actuation_reset.value()

            # Update group box that is shown
            if rapid_trigger_rb.isChecked():
                sub_options.setCurrentWidget(rt_options)
            else:
                sub_options.setCurrentWidget(fa_options)

        rapid_trigger_rb.toggled.connect(update_dict_from_options)
        sensitivity.valueChanged.connect(update_dict_from_options)
        top_deadzone.valueChanged.connect(update_dict_from_options)
        bottom_deadzone.valueChanged.connect(update_dict_from_options)
        actuation_point.valueChanged.connect(update_dict_from_options)
        actuation_reset.valueChanged.connect(update_dict_from_options)
        state.attach_listener(
            "in_configs", update_options_from_dict)


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
        key_configs_grid.addWidget(QLabel(), 1, 0)
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
        bar_label = QLabel()
        bar_label.setStyleSheet(
            "font-size: 11px;"
        )
        bar_label.setText("0.0 mm")
        bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar_label.setBuddy(bar)
        bar_vbox = QVBoxLayout()
        bar_vbox.addWidget(bar_label)
        bar_vbox.addWidget(bar)

        # Set up switch icon
        # The switch is divided in 3 to create an
        # up and down motion
        switch_top = QPixmap("../assets/switch_top.png").scaledToWidth(130)
        switch_top_label = QLabel()
        switch_top_label.setPixmap(switch_top)

        switch_mid = QPixmap("../assets/switch_mid.png").scaledToWidth(130)
        switch_mid_label = QLabel()
        switch_mid_label.setPixmap(switch_mid)
        switch_mid_label.setFixedHeight(50)

        switch_bottom = QPixmap("../assets/switch_bottom.png").scaledToWidth(130)
        switch_bottom_label = QLabel()
        switch_bottom_label.setPixmap(switch_bottom)
        switch_bottom_label.setStyleSheet(
            "padding: 0 0 15 0"
        )

        switch_vbox = QVBoxLayout()
        switch_vbox.addStretch()
        switch_vbox.addWidget(switch_top_label)
        switch_vbox.addWidget(switch_mid_label)
        switch_vbox.addWidget(switch_bottom_label)

        # Populate grid
        grid = QGridLayout()
        grid.addLayout(bar_vbox, 0, 0)
        grid.addLayout(switch_vbox, 0, 1)
        self.setLayout(grid)

        def update_bar_contents(info):
            distance = info[state.key_selected]["distance"]
            bar.setValue(round(distance * 100))
            bar_label.setText("{:.1f}".format(distance) + "mm" )
            switch_mid_label.setFixedHeight(round(50-50*distance/4))

            # Update color
            if info[state.key_selected]["state"]:
                bar.setStyleSheet(
                    "QProgressBar::chunk{background-color: #B2CFFF}")
            else:
                bar.setStyleSheet(
                    "QProgressBar::chunk{background-color: #555555}")

        state.attach_listener(
            "info", update_bar_contents)


class MainWindow(QMainWindow):
    """
    Main aplication window
    """

    def __init__(self):
        super(MainWindow, self).__init__()
        state = State()
        self.state = state
        state.in_configs = {}
        state.out_configs = {}

        # Use local qss
        self.setStyleSheet(open("style.qss", "r").read())

        # Add a grid
        self.root_grid = QGridLayout()
        self.root_window = QWidget()
        self.root_window.setLayout(self.root_grid)
        self.setCentralWidget(self.root_window)

        # Create widgets
        switch_icon = QPixmap("../assets/switch.png")
        switch_label = QLabel()
        switch_label.setPixmap(switch_icon)
        general_info = GeneralInfo(state)
        general_configs = GeneralConfigs(state)
        key_configs = KeyConfigs(state)
        visualizer = Visualizer(state)

        # Lower side
        save_button = QPushButton("&Save", self)
        save_button.clicked.connect(self.send_configs_to_pico)
        kz_icon = QPixmap("../assets/kz_icon.jpeg").scaled(32,32)
        kz_label = QLabel()
        kz_label.setStyleSheet(
            "border: 2px solid #B2CFFF;"
        )
        kz_label.setFixedWidth(36)
        kz_label.setPixmap(kz_icon)

        degen_icon = QPixmap("../assets/degen_icon.png").scaled(32,32)
        degen_label = QLabel()
        degen_label.setStyleSheet(
            "border: 2px solid #B2CFFF;"
        )
        degen_label.setFixedWidth(36)
        degen_label.setPixmap(degen_icon)

        lower_side = QHBoxLayout()
        lower_side.addWidget(kz_label)
        lower_side.addWidget(save_button)
        lower_side.addWidget(degen_label)

        # Populate grid
        self.root_grid.addWidget(general_info, 0, 0)
        self.root_grid.addWidget(general_configs, 1, 0)
        self.root_grid.addWidget(key_configs, 0, 1)
        self.root_grid.addWidget(visualizer, 1, 1)
        self.root_grid.addLayout(lower_side, 2, 0, 1, 2)

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
        timer2.start(16)

    def send_configs_to_pico(self):
        """
        Sends a configs to the pico to be rewritten
        """
        try:
            # Temp code until key configs are also updated
            configs_dict = self.state.in_configs
            configs_dict["general"] = self.state.out_configs["general"]
            configs_json = json.dumps(configs_dict)
            self.rpp.write((configs_json + "\n").encode())
        except:
            pass

    def update_open_port(self, port):
        """
        Opens a new port and closes the last one
        """
        try:
            if self.rpp != None:
                self.rpp.close()
            self.rpp = serial.Serial(port, timeout=1)
            response = kzserial.get_response_from_request(self.rpp, "configs_request")
            self.state.in_configs = response
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
