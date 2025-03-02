"""
Permet de gérer les environnements matériels
"""

import os
import platform

def is_dev():
    if os.path.exists("DEV") or os.environ.get("DEV", False):
        return True
    return False

def is_debug():
    if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
        return True
    return False

def is_raspberry_pi():
    if os.path.exists("/sys/firmware/devicetree/base/model"):
        with open("/sys/firmware/devicetree/base/model", "r", encoding="utf-8") as f:
            if "Raspberry Pi" in f.read():
                return True
    return False


def get_os():
    if is_raspberry_pi():
        return "Raspberry"
    if platform.system() == "Darwin":
        return "MacOS"

    return "Linux"


if __name__ == "__main__":
    print(get_os())
