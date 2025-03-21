"""Miscellaneous functions"""

import sys
import json
import datetime
from subprocess import run
from time import sleep

# import logging

from DateUtils import GetCurrentDate
from WittyPython import is_WittyPi_3

from OSUtils import is_raspberry_pi, has_MEGA4

# pylint: disable=ungrouped-imports
# pylint: disable=import-error
# Impossible de grouper les imports car les imports conditionnels ne sont pas supportés
if is_raspberry_pi():
    from RPi import GPIO
else:
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
UHUBCTL = "/usr/sbin/uhubctl"
USB_DIR = "/media/pi/Image"
LOG_DIR = "Log"

# Pour le mode config
# Bouton poussoir config
# pins BCM
if is_WittyPi_3():
    ConfigPin = 17  # pin physique 11
else:
    ConfigPin = 16  # pin physique 36 + ground 34

# Pour la carte USB Big 7
# Pour le relai Banggood initial
# pins BCM
# Ch1Pin = 19  # Scanner1
# Ch2Pin = 26  # Scanner2
# Ch3Pin = 20  # Scanner3
# Ch4Pin = 21  # Clé 4G

# Pour le relai SBComponent RelayPi-V2
# pins BCM
Ch1Pin = 19  # Scanner1
Ch2Pin = 13  # Scanner2
# Attention pour ces 2 pins, il faut supprimer les jumpers jaunes
# et cabler GPIO 27 et 22 (board pins 13 et 15) sur les relais avec des cables Dupont
Ch3Pin = 22  # Scanner3
Ch4Pin = 27  # Clé 4G
PinArray = [Ch1Pin, Ch2Pin, Ch3Pin, Ch4Pin]


def getChPin(i_scan: int):
    if 0 <= i_scan < 4:
        # print(f"getChPin: {i_scan} => {PinArray[i_scan]}")
        return PinArray[i_scan]

    print(f"La valeur passee doit être comprise entre 0 et 4, ici: {i_scan}")
    return -1


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
    except IOError as e:
        print(f"IOError: {e}")
        return 1
    return 0


def initDisplayFile():
    try:
        with open(DISPLAY_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except IOError as e:
        print(f"IOError: {e}")
        return 1
    return 0


def WriteDisplayFile(data, time):
    try:
        # print(data)
        text = time + " : " + str(data)
        with open(DISPLAY_FILE, "a", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    except IOError as e:
        print(f"IOError: {e}")
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
    except IOError as e:
        print(f"IOError: {e}")
        return 1
    return 0

def EndGPIO():
    if not is_raspberry_pi():
        return
    GPIO.cleanup()
    return


def InitGPIO():
    if not is_raspberry_pi():
        return 0
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        if not has_MEGA4():
            for i_pin in PinArray:
                GPIO.setup(i_pin, GPIO.OUT)
            # On n'arrête pas la clé 4G
            GPIO.output(PinArray[3], GPIO.HIGH)
            for i in range(0, 3):
                print(f"Initialisation du GPIO: {PinArray[i]}")
                GPIO.output(PinArray[i], GPIO.LOW)
    except IOError as e:
        print(f"IOError: {e}")
        return 1
    return 0


def TurnUsbOn(i_scan, time):
    if has_MEGA4():
        # On utilise le Hub 1-1
        # Les ports USB sont numérotés à partir de 1 avec uhubctl
        cmd = f"{UHUBCTL} -a on -p {i_scan + 1} -l 1-1"
        run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
        if is_raspberry_pi():
            sleep(time)
    else:
        try:
            realpin = getChPin(i_scan)
            GPIO.output(realpin, GPIO.HIGH)
            # Pour l'ancienne carte Relai
            # GPIO.output(realpin, GPIO.LOW)
            if is_raspberry_pi():
                sleep(time)
        except IOError:
            return 1
    return 0


def TurnUsbOff(i_scan):
    if has_MEGA4():
        # Les ports USB sont numérotés à partir de 1 avec uhubctl
        cmd = f"{UHUBCTL} -a off -p {i_scan + 1} -l 1-1"
        run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    else:
        try:
            realpin = getChPin(i_scan)
            GPIO.output(realpin, GPIO.LOW)
            # Pour l'ancienne carte Relai
            # GPIO.output(realpin, GPIO.HIGH)
        except IOError:
            return 1
    return 0


def ReadGPIOConfig():
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ConfigPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state_ = GPIO.input(ConfigPin)
    except IOError as e:
        print(f"IOError: {e}")
        state_ = 1

    print(f"Etat GPIO {ConfigPin}: {state_}")
    WriteTimeLogfile(f"Etat GPIO {ConfigPin}: {state_}")
    return state_


def WriteStartDateConfig(NextStartDate):
    data = {
        "NextStartDate1": NextStartDate[0],
        "NextStartDate2": NextStartDate[1],
        "NextStartDate3": NextStartDate[2],
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
    NextStartDate = [
        "2025-01-01T00:05:00Z",
        "2025-01-01T00:05:00Z",
        "2025-01-01T00:05:00Z",
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

    return NextStartDate


def CopyLog():
    # copy log folder to USB
    cmd = "sudo cp -r " + LOG_DIR + " " + USB_DIR
    # print(cmd)
    run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    # print(result.returncode,result.stdout,result.stderr)


if __name__ == "__main__":
    print("Test unitaire Miscellaneous")
    print(f"{NEXT_DATE_FILE}: {ReadStartDateConfig()}")
    InitGPIO()
    ReadGPIOConfig()
    initDisplayFile()
    WriteTimeLogfile("Test unitaire main de Miscellaneous")
    value = input("Voulez-vous modifier l'état des GPIO ? [Non=Entrée, sinon, Oui=o]: ")
    if not value:
        sys.exit(0)
    try:
        # On allume la clé 4G
        TurnUsbOn(3, 5)
        for int_scan in [0, 1, 2]:
            value = input(
                f"Basculer Scanner-{int_scan + 1} ? [Non=Entrée, sinon, Oui=o]: "
            )
            if value == "o":
                GPIO.setup(getChPin(int_scan), GPIO.OUT)
                state = GPIO.input(getChPin(int_scan))
                GPIO.output(getChPin(int_scan), not state)
                print(
                    f"  bascule Scanner-{int_scan + 1} pin {getChPin(int_scan)} {not state}"
                )
    except RuntimeError as e:
        print(f"RuntimeError: {e}")
        EndGPIO()
        sys.exit(0)
    except GPIO.Error as e:
        print(f"GPIO Error: {e}")
        EndGPIO()
        sys.exit(0)
