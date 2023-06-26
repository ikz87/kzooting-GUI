import serial
import sys
import glob
import json


def get_serial_ports():
    """
    Returns a list of all serial  ports
    that *can* be open
    """
    if sys.platform.startswith("win"):
        ports = ["COM%s" % (i + 1) for i in range(256)]
    elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob("/dev/tty[A-Za-z]*")
    elif sys.platform.startswith("darwin"):
        ports = glob.glob("/dev/tty.*")
    else:
        raise EnvironmentError("Unsupported platform")

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass

    return result


def read_dict_from_port(port):
    """
    Reads a dictionary from the port provided
    """
    line = port.readline().decode()
    return json.loads(line)


def get_response_from_request(port, request):
    """
    Sends a request to the pico and waits until
    it responds to that request with an
    adequate message
    """
    port.write((request + "\n").encode())
    data = read_dict_from_port(port)
    return data
