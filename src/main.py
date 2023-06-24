import kzserial
import sys
import serial
import kthread
import threading
import time
import inotify.adapters
import json
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt


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
    def __init__(self):
        super(KeyConfigs, self).__init__()

        # Add grid
        self.key_configs_grid = QGridLayout()
        self.setLayout(self.key_configs_grid)

        # Set up dropdown menu for keys
        self.keys_menu = QComboBox()
        for i in range(9):
            self.keys_menu.addItem(f"key_{i+1}")

            # Populate grid
            self.key_configs_grid.addWidget(self.keys_menu, 0, 0)


class Visualizer(QWidget):
    """
    Bottom right quadrant of the window
    """
    def __init__(self):
        super(Visualizer, self).__init__()

        # Add grid
        self.visualizer_grid = QGridLayout()
        self.setLayout(self.visualizer_grid)

        # Set up progress bar
        self.visualizer_bar = QProgressBar()
        self.visualizer_bar.setTextVisible(False)
        self.visualizer_bar.setOrientation(Qt.Vertical)
        self.visualizer_bar.setMaximum(400)
        self.visualizer_bar.setMinimum(0)
        self.visualizer_bar.setInvertedAppearance(True)

        # Set up switch icon
        self.switch_icon = QPixmap("../assets/switch.png")
        self.switch_label = QLabel()
        self.switch_label.setPixmap(self.switch_icon)

        # Populate grid
        self.visualizer_grid.addWidget(self.visualizer_bar, 0, 0)
        self.visualizer_grid.addWidget(self.switch_label, 0, 1)


class MainWindow(QMainWindow):
    """
    Main aplication window
    """
    def __init__(self):
        super(MainWindow, self).__init__()

        # Add a grid
        self.root_grid = QGridLayout()
        self.root_window = QWidget()
        self.root_window.setLayout(self.root_grid)
        self.setCentralWidget(self.root_window)

        # Create widgets
        self.key_configs = KeyConfigs()
        self.key_configs.keys_menu.currentIndexChanged.connect(self.update_selected_key)
        self.general_configs = GeneralConfigs()
        self.general_configs.ports_menu.textActivated.connect(self.update_selected_port)
        self.visualizer = Visualizer()

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
                key_distance = keys_info[self.key_selected]["distance"]
                self.visualizer.visualizer_bar.setValue(round(key_distance*100))
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
