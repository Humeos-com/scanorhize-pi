#!/usr/bin/env python3
"""Miscellaneous functions"""

import sys
from subprocess import run, SubprocessError, CalledProcessError
from time import sleep
import socket
import requests

from DateUtils import GetCurrentDate
from WittyPy_utilities import (
    is_WittyPi_4_L3V7,
    get_input_voltage,
    get_output_voltage,
    get_power_mode,
)
from ConfigApp import getLogger, getBatteryFile, getDisplayFile, getScanorhizeServer
from OSUtils import is_raspberry_pi
from gpio_utils import (
    init_gpio,
    end_gpio,
    enable_4g,
    disable_4g,
    turn_usb_on,
    turn_usb_off,
    read_gpio_config,
    read_gpio_input,
    read_gpio_output,
)
from pin_config import get_ch_pin, CHRG_PIN, STDBY_PIN


def chaineIntwitherror(chaine, valueerror, valuemin, valuemax):
    try:
        tmp = int(chaine, 10)
    except ValueError:
        tmp = valueerror
    tmp = max(tmp, valuemin)
    tmp = min(tmp, valuemax)
    return tmp


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
        return ReadGPIOInput(CHRG_PIN)
    return 0


def getStandbyStatus():
    """for the WittyPi L3V7"""
    if is_WittyPi_4_L3V7():
        return ReadGPIOInput(STDBY_PIN)
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
        # Calcul historique, à 3,3V on est encore à 30%
        # Cap = round((Volt - 2.7) / 1.49 * 100, 2)

        # A 3,5V on est à 0% et à 3,9 on est à 100%
        # ce qui est plus proche de la réalité
        # A 3.1V le Witty coupe l'alimentation
        Cap = round((Volt - 3.5) / 0.4 * 100, 2)
        if Cap < 0:
            Cap = 0
        if Cap > 100:
            Cap = 100
        return (Volt, Cap)

    # On est dans le cas d'une alimentation USB (Power Bank ou alimentation)
    # La power bank a un redresseur 5V, donc on ne connaît pas son voltage interne
    Volt = get_output_voltage()
    Cap = 100.0
    return (Volt, Cap)


def EndGPIO():
    """Clean up GPIO"""
    return end_gpio()


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
        print(f"    → Humeos Ping OK")
        return 1
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("Ping Error: %s", e)
    return 0


def enable4G():
    """Allume le port USB de la clé 4G"""
    return enable_4g()


def disable4G():
    """Eteint le port USB de la clé 4G"""
    return disable_4g()


def check_network_route(timeout=3):
    """
    Check whether the device has a basic network route available.

    Attempts to open a TCP connection to a reliable external server
    (Cloudflare DNS: 1.1.1.1 on port 53).

    This verifies:
    - the network interface is up,
    - routing is available,
    - outbound traffic is possible.

    It does NOT guarantee that full Internet access or DNS resolution works.
    """
    
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=timeout)
        print(f"    → Network route OK")
        return True
    except OSError:
        return False


def check_http_connection(url="https://clients3.google.com/generate_204", timeout=5):
    """
    Check whether full Internet access is available.

    Sends an HTTP GET request to a lightweight endpoint expected
    to return HTTP status code 204 (No Content).

    This verifies:
    - DNS resolution,
    - TCP connectivity,
    - HTTPS communication,
    - real Internet access.
    """
    
    try:
        response = requests.get(url, timeout=timeout)
        print(f"    → Google 204 OK")
        return response.status_code == 204

    except requests.RequestException:
        return False


def check_connectivity(max_attempts=25, min_number_of_successes=1):
    print("checking connectivity....")
        
    for attempt in range(1, max_attempts + 1):

        # Step 1: Check network route
        if not check_network_route():
            print(f"    → [{attempt}/{max_attempts}] No network route")
            sleep(5)
            continue

        # Step 2: Check Internet access
        if not check_http_connection():
            print(f"    → [{attempt}/{max_attempts}] HTTP connection failed")
            sleep(5)
            continue
            
        # Step 3: Ping Humeos server
        if not pingAPI(getScanorhizeServer()):
            print(f"    → [{attempt}/{max_attempts}] Humeos Ping failed")
            sleep(5)
            continue

        min_number_of_successes -= 1
        if min_number_of_successes > 0:
            print(f"    → [{attempt}/{max_attempts}] Internet OK... but let's try it again {min_number_of_successes} more time"
                f"{'s' if min_number_of_successes > 1 else ''}..."
            )
            sleep(5)
            continue
        
        print(f"    → [{attempt}/{max_attempts}] Internet OK")
        return True
        


    # Failes to get Internet connection
    getLogger().error("Impossible d'avoir de la connectivité, on arrête !")
    raise RuntimeError("Pas de connectivité !")


def InitGPIO():
    """Fonction historique pour les port USB"""
    return init_gpio()


def TurnUsbOn(i_scan, time):
    """Turn on USB port for scanner"""
    return turn_usb_on(i_scan, time)


def TurnUsbOff(i_scan, delay=0):
    """Turn off USB port for scanner"""
    return turn_usb_off(i_scan, delay)


def ReadGPIOConfig():
    """Read the GPIO configuration"""
    return read_gpio_config()


def ReadGPIOInput(pin: int):
    """Read the GPIO input"""
    return read_gpio_input(pin)


def ReadGPIOOutput(pin: int):
    """Read the state of a GPIO output pin"""
    return read_gpio_output(pin)


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
                state = ReadGPIOOutput(get_ch_pin(int_scan))
                if state:
                    TurnUsbOff(int_scan, 1)
                else:
                    TurnUsbOn(int_scan, 1)
                print(
                    f"  bascule Scanner-{int_scan + 1} pin {get_ch_pin(int_scan)} {state}"
                )
    except RuntimeError as e:
        print(f"RuntimeError: {e}")
        EndGPIO()
        sys.exit(1)

    # disable4G()
    # le EndGPIO remet les GPIO dans l'état d'origine, il éteint donc les relais
    # ce qu'on ne veut pas si on doit scanner...
    # EndGPIO()
    sys.exit(0)
