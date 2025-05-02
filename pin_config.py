"""
Configuration des pins GPIO pour les scanners
"""

import json
from os import path
from WittyPython import is_WittyPi_3
from ConfigApp import getConfigHubFile, getLogger

# Charging and standby pins for WittyPi
CHRG_PIN: int = 5  # input to detect charging status
STDBY_PIN: int = 6  # input to detect standby status

# Configuration button pin
if is_WittyPi_3():
    CONFIG_PIN = 17  # pin physique 11
else:
    CONFIG_PIN = 16  # pin physique 36 + ground 34

# Pour le relai Banggood initial
# pins BCM
# Ch1Pin = 19  # Scanner1
# Ch2Pin = 26  # Scanner2
# Ch3Pin = 20  # Scanner3
# Ch4Pin = 21  # Clé 4G
# PinArray = [19, 26, 20, 21]

# Pour le relai SBComponent RelayPi-V2
# pins BCM
# Ch1Pin = 19  # Scanner1
# Ch2Pin = 13  # Scanner2
# Attention pour ces 2 pins, il faut supprimer les jumpers jaunes
# et cabler GPIO 27 et 22 (board pins 13 et 15) sur les relais avec des cables Dupont
# Ch3Pin = 22  # Scanner3
# Ch4Pin = 27  # Clé 4G
# PinArray = [19, 13, 22, 27]
# configuration des ports USB de la carte Big 7
DEFAULT_PIN_ARRAY = [13, 22, 27, 19]


def get_pin_array():
    """
    Get the pin array configuration from Hub.json.
    If the file doesn't exist or doesn't contain PinArray, return the default configuration.

    Returns:
        list: Array of pin numbers for each scanner
    """
    try:
        hub_file = getConfigHubFile()
        if path.exists(hub_file):
            with open(hub_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "PinArray" in config:
                    return config["PinArray"]
                getLogger().error("PinArray key not found in Hub.json")
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        getLogger().error("Error loading pin array from Hub.json: %s", e)

    return DEFAULT_PIN_ARRAY


def get_ch_pin(i_scan: int):
    """
    Get the pin number for a given scanner index

    Args:
        i_scan (int): Scanner index (0-based)

    Returns:
        int: Pin number for the scanner
    """
    pin_array = get_pin_array()
    if 0 <= i_scan < len(pin_array):
        return pin_array[i_scan]
    return None
