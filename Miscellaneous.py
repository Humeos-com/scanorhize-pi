"""Miscellaneous functions"""

import json
import datetime
from subprocess import run
from time import sleep

from DateUtils import GetCurrentDate

from OSUtils import is_raspberry_pi

# pylint: disable=ungrouped-imports
# pylint: disable=import-error
# Impossible de grouper les imports car les imports conditionnels ne sont pas supportés
if is_raspberry_pi():
    from RPi import GPIO
else:
    import sys
    import fake_rpi

    sys.modules["RPi"] = fake_rpi.RPi  # Mock RPi module
    sys.modules["RPi.GPIO"] = fake_rpi.RPi.GPIO
    sys.modules["smbus"] = fake_rpi.smbus
    from RPi import GPIO

LOG_DIR = "Log"
CONFIG_DIR = "ConfigFile"
NEXT_DATE_FILE = CONFIG_DIR + "/NextStartDate.json"
DISPLAY_FILE = LOG_DIR + "/Display.txt"
BATTERY_FILE = LOG_DIR + "/Batterie.txt"


Ch1Pin = 19
Ch2Pin = 26
Ch3Pin = 20
Ch4Pin = 21
PinArray = [Ch1Pin, Ch2Pin, Ch3Pin, Ch4Pin]


def getCh1Pin():
    return Ch1Pin


def getCh2Pin():
    return Ch1Pin


def getCh3Pin():
    return Ch1Pin


def getCh4Pin():
    return Ch1Pin


def chaineIntwitherror(chaine, valueerror, valuemin, valuemax):
    try:
        tmp = int(chaine, 10)
    except ValueError:
        tmp = valueerror
    tmp = max(tmp, valuemin)
    tmp = min(tmp, valuemax)
    return tmp


def checkchaine(chaine, valueerror):
    tmp = isinstance(chaine, str)
    print("is a chaine: ", tmp)
    if tmp:
        return chaine
    return valueerror


def WriteLogFile(data):
    print(data)
    try:
        now = datetime.datetime.utcnow()
        filename = now.strftime(LOG_DIR + "/Scanorhize_%Y-%m-%d.txt")
        with open(filename, "a", encoding="utf-8") as f:
            f.write(data + "\n")

    except ValueError:
        return 1
    return 0


def initDisplayFile():
    with open(DISPLAY_FILE, "w", encoding="utf-8") as f:
        f.write("")
    return 0


def WriteDisplayFile(data, time):
    try:
        # print(data)
        text = time + " : " + str(data)
        with open(DISPLAY_FILE, "a", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    except ValueError:
        return 1
    return 0


def WriteTimeLogfile(data):
    date = GetCurrentDate()
    try:
        Time = date + " : " + str(data)
        WriteLogFile(Time)
        WriteDisplayFile(data, date)
    except ValueError:
        return 1
    return date


def WriteBatterieFile(Volt, Cap):
    print(Volt, " ", Cap)
    try:
        date = GetCurrentDate()
        text = date + ": " + str(Volt) + " " + str(Cap)
        with open(BATTERY_FILE, "a", encoding="utf-8") as f:
            f.write(text)
            f.write("\r\n")
    except ValueError:
        return 1
    return 0


def InitGPIO():
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(Ch1Pin, GPIO.OUT)  # Scanner1
        GPIO.setup(Ch2Pin, GPIO.OUT)  # Scanner2
        GPIO.setup(Ch3Pin, GPIO.OUT)  # Scanner3
        GPIO.setup(Ch4Pin, GPIO.OUT)  # Clé 4g
        GPIO.output(Ch1Pin, GPIO.HIGH)
        GPIO.output(Ch2Pin, GPIO.HIGH)
        GPIO.output(Ch3Pin, GPIO.HIGH)
    except IOError as e:
        print(f"IOError: {e}")
        return 1
    # GPIO.output(Ch4Pin, GPIO.HIGH)
    return 0


def TurnUSBPin_On(pin, time):
    cmd = "echo '1-1'|sudo tee /sys/bus/usb/drivers/usb/unbind"
    run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    TurnPin_On(pin, 1)
    cmd = "echo '1-1'|sudo tee /sys/bus/usb/drivers/usb/bind"
    run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    sleep(time)
    return 0


def TurnPin_On(pin, time):
    try:
        realpin = PinArray[pin]
        GPIO.output(realpin, GPIO.LOW)
        sleep(time)
    except IOError:
        return 1
    return 0


def TurnPin_Off(pin):
    try:
        realpin = PinArray[pin]
        GPIO.output(realpin, GPIO.HIGH)
    except IOError:
        return 1
    return 0


def ReadGPIOConfig():
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.IN)
        state = GPIO.input(17)
    except IOError:
        state = 1
    WriteTimeLogfile("etat :" + str(state))
    return state


def WriteStartDateConfig(NextStartDate, NextStartseconds):
    data = {
        "NextStartDate1": NextStartDate[0],
        "NextStartDate2": NextStartDate[1],
        "NextStartDate3": NextStartDate[2],
        "NextTime1": NextStartseconds[0],
        "NextTime2": NextStartseconds[1],
        "NextTime3": NextStartseconds[2],
    }
    try:
        json_object = json.dumps(data, indent=len(data))
        with open(NEXT_DATE_FILE, "w", encoding="utf-8") as outfile:
            outfile.write(json_object)
    except ValueError:
        print("Error in write config file: ", NEXT_DATE_FILE)
        return 1

    return 0


def ReadStartDateConfig():
    NextStartseconds = [0, 0, 0]
    NextStartDate = [
        "2021-01-14T11:05:00Z",
        "2021-01-15T11:05:00Z",
        "2021-01-16T11:05:00Z",
    ]
    try:
        with open(NEXT_DATE_FILE, "r", encoding="utf-8") as openfile:
            data = json.load(openfile)
    except FileNotFoundError:
        WriteTimeLogfile("Error reading file: " + NEXT_DATE_FILE)

    else:
        NextStartDate[0] = data["NextStartDate1"]
        NextStartDate[1] = data["NextStartDate2"]
        NextStartDate[2] = data["NextStartDate3"]
        NextStartseconds[0] = data["NextTime1"]
        NextStartseconds[1] = data["NextTime2"]
        NextStartseconds[2] = data["NextTime3"]

    return NextStartDate, NextStartseconds


def CopyLog():
    # copy log folder to USB
    USBPath = "/media/pi/Image/"
    LogPath = "Log"
    cmd = "sudo cp -r " + LogPath + " " + USBPath
    # print(cmd)
    run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    # print(result.returncode,result.stdout,result.stderr)


if __name__ == "__main__":
    InitGPIO()
    initDisplayFile()
    WriteTimeLogfile("Test unitaire main de Miscellaneous")
