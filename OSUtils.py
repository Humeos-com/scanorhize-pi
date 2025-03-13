"""
Permet de gérer les environnements matériels
Singleton pour la configuration de l'application
"""

import os
import platform
import json
import logging
import usb.core


# Carte UUGEAR MEGA4
# 2109:2817 VIA Labs, Inc. USB2.0 Hub, USB 2.10, 4 ports, ppps
def get_MEGA4():
    with_MEGA4 = True
    try:
        dev = usb.core.find(idVendor=0x2109, idProduct=0x2817)
        if dev is None:
            print("Pas de carte MEGA4")
            with_MEGA4 = False
        logging.info("Logging initialized at level: %s", str(dev))
    except usb.core.NoBackendError:
        print("Pas de carte MEGA4")
        with_MEGA4 = False
    return with_MEGA4


class Config:
    """Permet de connaitre quel est l'environnement d'exécution du programme"""

    _instance = None  # Class variable to store the single instance
    environment = "PROD"
    log_level = "INFO"
    platform = "Linux"
    usb_mode = "GPIO"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):
        """Load config from environment variables or config.json"""

        # Try config.json if exists
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config_data = json.load(f)
                cls.environment = config_data.get("environment", cls.environment)
                cls.log_level = config_data.get("log_level", cls.log_level)
        except FileNotFoundError:
            pass  # Keep default values

        if os.path.exists("DEV") or os.environ.get("DEV", False):
            cls.environment = "DEV"
        if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
            cls.log_level = "DEBUG"

        # Try to get from environment variable
        cls.environment = os.getenv("APP_ENV", cls.environment)
        cls.log_level = os.getenv("LOG_LEVEL", cls.log_level)

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
    def _setup_logging(cls):
        """Configure logging based on environment"""
        log_level = logging.DEBUG if cls.log_level.upper() == "DEBUG" else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info("Logging initialized at level: %s", cls.log_level)

    @classmethod
    def is_dev(cls):
        if cls.environment == "DEV":
            return True
        return False

    @classmethod
    def is_debug(cls):
        if cls.log_level == "DEBUG":
            return True
        return False

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


def is_dev():
    return Config().is_dev()


def is_debug():
    return Config().is_debug()


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
    print(f"Dev: {is_dev()}")
    print(f"Debug: {is_debug()}")
    print(f"Raspberry: {is_raspberry_pi()}")
    print(f"has MEGA4: {has_MEGA4()}")
