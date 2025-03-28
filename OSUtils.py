"""
Permet de gérer l'environnement matériel OS, cartes, etc.
Utilise le pattern Singleton pour stocker la configuration
"""

import os
import platform
import usb.core

from ConfigApp import getLogger


# Carte UUGEAR MEGA4
# 2109:2817 VIA Labs, Inc. USB2.0 Hub, USB 2.10, 4 ports, ppps
def get_MEGA4():
    with_MEGA4 = True
    try:
        dev = usb.core.find(idVendor=0x2109, idProduct=0x2817)
        if dev is None:
            with_MEGA4 = False
    except usb.core.NoBackendError:
        with_MEGA4 = False
    if with_MEGA4:
        getLogger().warning("Carte MEGA4 détectée")
    else:
        getLogger().warning("Pas de carte MEGA4 détectée")
    return with_MEGA4


class Config:
    """Permet de connaitre l'environnement matériel du Hub"""

    _instance = None  # Class variable to store the single instance
    platform: str = "Linux"
    usb_mode: str = "GPIO"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):

        if os.path.exists("/sys/firmware/devicetree/base/model"):
            with open(
                "/sys/firmware/devicetree/base/model", "r", encoding="utf-8"
            ) as f:
                if "Raspberry Pi" in f.read():
                    cls.platform = "Raspberry"

        if get_MEGA4():
            cls.usb_mode = "MEGA4"
        else:
            cls.usb_mode = "GPIO"

    @classmethod
    def is_raspberry_pi(cls):
        if cls.platform == "Raspberry":
            return True
        return False

    @classmethod
    def has_MEGA4(cls):
        if cls.usb_mode == "MEGA4":
            return True
        return False


def is_raspberry_pi():
    return Config().is_raspberry_pi()


def get_os():
    if is_raspberry_pi():
        return "Raspberry"
    if platform.system() == "Darwin":
        return "MacOS"
    return "Linux"


def has_MEGA4():
    return Config().has_MEGA4()


if __name__ == "__main__":
    print(get_os())
    print(f"Raspberry: {is_raspberry_pi()}")
    print(f"has MEGA4: {has_MEGA4()}")
    print(f"Raspberry: {is_raspberry_pi()}")
    print(f"has MEGA4: {has_MEGA4()}")
