import kzserial
import sys
import serial
import threading
import time
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt


class Filler(QLabel):
   def __init__(self):
      super(Filler, self).__init__()
      self.setText("Some filler")


class GeneralConfigs(QWidget):
   def __init__(self):
      super(GeneralConfigs, self).__init__()

      # Add grid
      self.general_configs_grid = QGridLayout()
      self.setLayout(self.general_configs_grid)

      # Set up dropdown menu for ports
      # This will be updated from another thread
      self.ports_menu = QComboBox()
      self.ports_menu.addItem("Select port")

      # Populate grid
      self.general_configs_grid.addWidget(self.ports_menu, 0, 0)


class KeyConfigs(QWidget):
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
   def __init__(self):
      super(MainWindow, self).__init__()
      self.is_open = True

      # Add a grid
      self.root_grid = QGridLayout()
      self.root_window = QWidget()
      self.root_window.setLayout(self.root_grid)
      self.setCentralWidget(self.root_window)

      # Add widgets
      self.key_configs = KeyConfigs()
      self.key_configs.keys_menu.currentIndexChanged.connect(self.update_selected_key)
      self.general_configs = GeneralConfigs()
      self.general_configs.ports_menu.textActivated.connect(self.update_selected_port)
      self.general_configs.ports_menu.textActivated.connect(self.update_ports)
      self.visualizer = Visualizer()

      # Populate grid
      self.root_grid.addWidget(Filler(), 0, 0)
      self.root_grid.addWidget(self.key_configs, 0, 1)
      self.root_grid.addWidget(self.general_configs, 1, 0)
      self.root_grid.addWidget(self.visualizer, 1, 1)

      # Get keys information
      self.info_thread = threading.Thread(target=self.update_keys_info, args=())
      self.info_thread_flag = True
      self.info_thread.start()


      # Default selections
      self.update_ports()
      self.update_selected_port()
      self.key_selected = "key_1"
      self.rpp = None


   def update_keys_info(self):
      """
      Updates the keys info dict from a serial port
      """
      while True:
         # Return from thread
         if not self.info_thread_flag:
            return

         try:
            self.keys_info = kzserial.read_dict_from_port(self.rpp)
            key_distance = self.keys_info[self.key_selected]["distance"]
            #print(self.keys_info)
            self.visualizer.visualizer_bar.setValue(round(key_distance*100))

         except:
            time.sleep(0.1)


   def update_ports(self):
      """
      Updates the ports list
      """
      self.ports = kzserial.get_serial_ports()
      self.general_configs.ports_menu.clear()
      if len(self.ports) > 0:
         self.general_configs.ports_menu.addItems(self.ports)
      else:
         self.general_configs.ports_menu.addItem("No port selected")


   def update_selected_key(self):
      self.key_selected = self.key_configs.keys_menu.currentText()


   def update_selected_port(self):
      self.port_selected = self.general_configs.ports_menu.currentText()
      try:
         self.rpp = serial.Serial(self.port_selected, timeout=0.5)
      except (OSError, serial.SerialException):
         self.rpp = None



   def closeEvent(self, a0: QCloseEvent):
      self.is_open = False
      self.info_thread_flag = False
      self.info_thread.join()
      return super().closeEvent(a0)


def main():
   app = QApplication(sys.argv)
   main_window = MainWindow()
   main_window.show()
   sys.exit(app.exec())


if __name__ == '__main__':
   main()
