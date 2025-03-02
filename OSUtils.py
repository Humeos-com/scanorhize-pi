"""
Permet de gérer les environnements matériels
"""

import os
import platform

class env:
    ''' Permet de connaitre quel est l'environnement d'exécution du programme '''
    _instance = None  # Class variable to store the single instance
    environement = "PROD"
    mode = "QUIET"
    platform = "Linux"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(env, cls).__new__(cls)
            cls._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):
        if os.path.exists("DEV") or os.environ.get("DEV", False):
            cls.environement = "DEV"
        if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
            cls.mode = "DEBUG"
        if os.path.exists("/sys/firmware/devicetree/base/model"):
            with open("/sys/firmware/devicetree/base/model", "r", encoding="utf-8") as f:
                if "Raspberry Pi" in f.read():
                    cls.platform = "Raspberry"


    @classmethod
    def is_dev(cls):
        if cls.environement == "DEV":
            return True
        return False

    @classmethod
    def is_debug(cls):
        if cls.mode == "DEBUG":
            return True
        return False

    @classmethod
    def is_raspberry_pi(cls):
        if cls.platform == "Raspberry":
            return True
        return False

def is_dev():
    return env().is_dev()

def is_debug():
    return env().is_debug()

def is_raspberry_pi():
    return env().is_raspberry_pi()

def get_os():
    if is_raspberry_pi():
        return "Raspberry"
    if platform.system() == "Darwin":
        return "MacOS"
    return "Linux"


if __name__ == "__main__":
    print(get_os())
    print(f"Dev: {is_dev()}")
    print(f"Debug: {is_debug()}")
    print(f"Raspberry: {is_raspberry_pi()}")
