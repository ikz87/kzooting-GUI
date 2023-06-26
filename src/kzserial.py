from os import read
import serial
import sys
import glob
import json
from dataclasses import dataclass, is_dataclass, field, asdict
from dacite import from_dict

def get_serial_ports():
    """
    Returns a list of all serial  ports
    that *can* be open
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

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

    # Wait for a message that matches the request
    while True:
        message = read_dict_from_port(port)
        if message["message_type"] == request + "_response":
            break
    return message


@dataclass
class Response:
    message_type: str

@dataclass
class GeneralConfigs:
    rapid_trigger: bool
    sensitivity: float
    top_deadzone: float
    bootom_deadzone: float
    actuation_point: float
    actuation_reset: float


@dataclass
class KeyActions:
    actions: list[list[str]]


@dataclass
class ConfigsData:
    general: GeneralConfigs
    key_1: KeyActions
    key_2: KeyActions
    key_3: KeyActions
    key_4: KeyActions
    key_5: KeyActions
    key_6: KeyActions
    key_7: KeyActions
    key_8: KeyActions
    key_9: KeyActions

@dataclass
class ConfigsRequestResponse(Response, ConfigsData):
    message_type: str = field(default="configs_request_response", init=False)
