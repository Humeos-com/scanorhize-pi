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
        getLogger().warning("MEGA4 board detected")
    else:
        getLogger().warning("No MEGA4 board detected")
    return with_MEGA4


class Config:
    """Permet de connaitre l'environnement matériel du Hub
    Utilise le pattern Singleton pour stocker la configuration
    """

    _instance = None  # Class variable to store the single instance
    platform: str
    model: str
    usb_mode: str

    def __new__(cls):
        """Ensure only one instance is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Load the configuration data (runs only once)."""
        self.platform = "Linux"
        self.usb_mode = "GPIO"
        self.model = ""
        if os.path.exists("/sys/firmware/devicetree/base/model"):
            with open(
                "/sys/firmware/devicetree/base/model", "r", encoding="utf-8"
            ) as f:
                if "Raspberry Pi" in f.read():
                    self.platform = "Raspberry"
                    self.model = f.read()

        if get_MEGA4():
            self.usb_mode = "MEGA4"
        else:
            self.usb_mode = "GPIO"

    def is_raspberry_pi(self) -> bool:
        return self.platform == "Raspberry"

    def has_MEGA4(self) -> bool:
        return self.usb_mode == "MEGA4"

    def get_model(self) -> str:
        return self.model


def is_raspberry_pi():
    return Config().is_raspberry_pi()


def get_os():
    if is_raspberry_pi():
        return "Raspberry"
    if platform.system() == "Darwin":
        return "MacOS"
    return "Linux"


def get_model():
    return Config().get_model()


def has_MEGA4():
    return Config().has_MEGA4()


if __name__ == "__main__":
    print(get_os())
    print(f"Raspberry: {is_raspberry_pi()}")
    print(f"has MEGA4: {has_MEGA4()}")
    print(f"Raspberry: {is_raspberry_pi()}")
    print(f"has MEGA4: {has_MEGA4()}")
