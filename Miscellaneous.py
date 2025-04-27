"""Miscellaneous functions"""

import sys
from subprocess import run, SubprocessError, CalledProcessError
from time import sleep

# import logging

from DateUtils import GetCurrentDate
from WittyPython import (
    is_WittyPi_3,
    is_WittyPi_4_L3V7,
    get_input_voltage,
    get_output_voltage,
    get_power_mode,
)
from ConfigApp import getLogger, getBatteryFile, getDisplayFile, getScanorhizeServer
from ConfigApp import getUhubctl
from ConfigApp import getChPin

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

CHRG_PIN: int = 5  # input to detect charging status
STDBY_PIN: int = 6  # input to detect standby status

# Pour le mode config
# Bouton poussoir config
# pins BCM
if is_WittyPi_3():
    ConfigPin = 17  # pin physique 11
else:
    ConfigPin = 16  # pin physique 36 + ground 34


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


def initDisplayFile():
    try:
        with open(getDisplayFile(), "w", encoding="utf-8") as f:
            f.write("")
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 1
    return 0


def WriteDisplayFile(data, time):
    try:
        # print(data)
        text = time + " : " + str(data)
        with open(getDisplayFile(), "a", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    except IOError as e:
        print(f"IOError: {e}")
        return 1
    return 0


def WriteBatterieFile(Volt, Cap):
    print(Volt, " ", Cap)
    try:
        date = GetCurrentDate()
        text = date + ": " + str(Volt) + " " + str(Cap)
        with open(getBatteryFile(), "a", encoding="utf-8") as f:
            f.write(text)
            f.write("\r\n")
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 1
    return 0


def getChargingStatus():
    """for the WittyPi L3V7"""
    if is_WittyPi_4_L3V7():
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(CHRG_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        return GPIO.input(CHRG_PIN)
    return 0


def getStandbyStatus():
    """for the WittyPi L3V7"""
    if is_WittyPi_4_L3V7():
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(STDBY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        return GPIO.input(STDBY_PIN)
    return 0


def isWittyPiCharging():
    if is_WittyPi_4_L3V7():
        chrg = getChargingStatus()
        stdby = getStandbyStatus()
        if not chrg and stdby:
            # Charging battery
            return 1
        # Discharging battery
        return 0
    return 1


def ReadBatVoltCap():
    if not is_raspberry_pi():
        return (5.0, 99.0)

    if get_power_mode():
        # On est dans le cas d'un batterie interne
        # La formule provient de l'ancienne application...
        Volt = get_input_voltage()
        Cap = round((Volt - 2.7) / 1.49 * 100, 2)
        return (Volt, Cap)

    # On est dans le cas d'une alimentation USB (Power Bank ou alimentation)
    # La power bank a un redresseur 5V, donc on ne connaît pas son voltage interne
    Volt = get_output_voltage()
    Cap = 100.0
    return (Volt, Cap)


def EndGPIO():
    if not is_raspberry_pi():
        return
    GPIO.cleanup()
    return


def pingAPI(address):
    """Lance un ping unique. Le timeout par défaut sur Linux est de 10s

    Args:
        address (str): nom DNS ou IP

    Returns:
        int: 1 si address répond, 0 en cas d'erreur
    """
    try:
        run(["ping", "-c 1", address], capture_output=True, text=True, check=True)
        getLogger().warning("Ping OK: %s", address)
        return 1
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("Ping Error: %s", e)
    return 0


def enable4G():
    """Allume le port USB de la clé 4G"""
    if not is_raspberry_pi():
        return 1
    try:
        if not has_MEGA4():
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(getChPin(3), GPIO.OUT)
            GPIO.output(getChPin(3), GPIO.HIGH)
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 0
    return 1


def disable4G():
    """Eteint le port USB de la clé 4G"""
    if not is_raspberry_pi():
        return 1
    try:
        if not has_MEGA4():
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.output(getChPin(3), GPIO.LOW)
            GPIO.cleanup(getChPin(3))
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 0
    return 1


def check_connectivity(max_attempts=12):
    """Check connectivity to the server with retries"""
    res = 0
    iteration = 0
    while res == 0 and iteration < max_attempts:
        res = pingAPI(getScanorhizeServer())
        if is_raspberry_pi():
            sleep(5)
        iteration += 1
    if iteration == max_attempts:
        getLogger().error("Impossible d'avoir de la connectivité, on arrête !")
        raise RuntimeError("Pas de connectivité !")


def sync_time():
    """On synchronise l'horloge de la carte WittyPi avec le serveur"""
    try:
        cmd = "sudo ./TimeSynchronisation.sh"
        run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
        getLogger().warning("TimeSynchronisation.sh: OK")
        return 1
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("TimeSynchronisation.sh error: %s", e)
    return 0


def InitGPIO():
    """Fonction historique pour les port USB"""
    if not is_raspberry_pi():
        return 0
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        if not has_MEGA4():
            # On arrête les scanners
            for i_pin in range(0, 3):
                print(f"Initialisation du GPIO: {getChPin(i_pin)}")
                GPIO.setup(getChPin(i_pin), GPIO.OUT)
                GPIO.output(getChPin(i_pin), GPIO.LOW)
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 1
    return 0


def TurnUsbOn(i_scan, time):
    if has_MEGA4():
        # On utilise le Hub 1-1
        # Les ports USB sont numérotés à partir de 1 avec uhubctl
        cmd = f"{getUhubctl()} -a on -p {i_scan + 1} -l 1-1"
        run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
        if is_raspberry_pi():
            sleep(time)
    else:
        try:
            realpin = getChPin(i_scan)
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(realpin, GPIO.OUT)
            GPIO.output(realpin, GPIO.HIGH)
            # Pour l'ancienne carte Relai
            # GPIO.output(realpin, GPIO.LOW)
            if is_raspberry_pi():
                sleep(time)
        except IOError:
            return 1
    return 0


def TurnUsbOff(i_scan, delay=0):
    sleep(delay)
    if has_MEGA4():
        # Les ports USB sont numérotés à partir de 1 avec uhubctl
        cmd = f"{getUhubctl()} -a off -p {i_scan + 1} -l 1-1"
        run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    else:
        try:
            realpin = getChPin(i_scan)
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(realpin, GPIO.OUT)
            GPIO.output(realpin, GPIO.LOW)
            # Pour l'ancienne carte Relai
            # GPIO.output(realpin, GPIO.HIGH)
        except IOError as e:
            getLogger().error("IOError: %s", e)
            return 1
    return 0


def ReadGPIOConfig():
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ConfigPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state_ = GPIO.input(ConfigPin)
    except IOError as e:
        getLogger().error("IOError: %s", e)
        state_ = 1

    getLogger().warning("Etat GPIO %d: %d", ConfigPin, state_)
    return state_


if __name__ == "__main__":
    print("Test unitaire Miscellaneous")
    InitGPIO()
    ReadGPIOConfig()
    initDisplayFile()
    print(f"Is charging? {isWittyPiCharging()}")
    print(f"Volts: {ReadBatVoltCap()[0]} Capacity: {ReadBatVoltCap()[1]}")
    value = input("Voulez-vous modifier l'état des GPIO ? [Non=Entrée, sinon, Oui=o]: ")
    if not value:
        sys.exit(0)
    try:
        # On allume la clé 4G
        enable4G()
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

    disable4G()
    # le EndGPIO remet les GPIO dans l'état d'origine, il éteint donc les relais
    ## EndGPIO()
