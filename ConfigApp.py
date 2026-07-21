#!/usr/bin/env python3
"""
Permet de gérer l'environnement matériel OS, cartes, etc.
Utilise le pattern Singleton pour stocker la configuration
"""

import os
import json
import logging
from datetime import datetime
from utils import write_json_to_file


# Path to the config file
CONFIG_APP_FILE = os.path.expanduser("~/.scanorhize")


class ConfigApp:
    """Class to hold configuration data"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigApp, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the instance if not already initialized."""
        if hasattr(self, "initialized"):  # Skip if already initialized
            return

        # First handle app environment
        self.environment = os.getenv("APP_ENV", "PROD")
        if self.environment == "DEV":
            self.config_app_file = f"{CONFIG_APP_FILE}-dev.json"
        else:
            self.config_app_file = f"{CONFIG_APP_FILE}-prod.json"

        if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
            self.log_level = "DEBUG"
        else:
            self.log_level = "INFO"

        # Type hints for required attributes
        self.config_app_file: str
        self.log_dir: str = "Log"
        self.config_dir: str = "ConfigFile"
        self.config_hub_file: str = "Hub.json"
        self.display_file: str = "Display.txt"
        self.battery_file: str = "Battery.txt"
        self.uhubctl: str = "/usr/sbin/uhubctl"
        self.usb_dir: str = "/media/pi/Image"
        self.image_dir: str = "images"
        self.s3_bucket: str = "s3://humeos-images-landing"
        self.scanorhize_server: str = "backend-prod.humeos.com"
        self.offline: bool = False
        self.th_x: int = 512
        self.th_y: int = 704
        self.load_config()
        self._setup_logging()

        self.initialized = True
        
        import sys
        if os.path.basename(sys.argv[0]).startswith("ScanorhizeStart"):
            self.logger.info("============= START =============")
            self.logger.info("Read configuration from %s", self.config_app_file)

    def _setup_logging(self):
        log_file = os.path.join(
            os.path.expanduser(self.log_dir),
            f"Scanorhize_{datetime.now():%Y-%m-%d}.log",
        )
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self.logger = logging.getLogger("MainLogger")
        self.logger.setLevel(logging.DEBUG if self.log_level.upper() == "DEBUG" else logging.INFO)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(lineno)04d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        self.logger.addHandler(fh)

    def load_config(self):
        """Load config and update attributes dynamically"""
        if not os.path.exists(self.config_app_file):
            return
        try:
            with open(self.config_app_file, "r", encoding="utf-8") as openfile:
                for key, value in json.load(openfile).items():
                    if key != "logger":
                        setattr(self, key, value)
        except (FileNotFoundError, ValueError):
            pass

    def json(self):
        """Convert object to JSON, excluding special attributes"""
        data = {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_")
            and key != "logger"
            and key != "config_app_file"
            and key != "initialized"
        }
        return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=4)

    def save_config(self):
        """Save the current configuration to a JSON file."""
        json_data = self.json()
        return write_json_to_file(self.config_app_file, json_data)

    def is_prod(self) -> bool:
        """Returns True if environment is set to PROD."""
        return self.environment.upper() == "PROD"

    def is_dev(self) -> bool:
        """Returns True if environment is set to DEV."""
        return self.environment.upper() == "DEV"

    def is_debug(self) -> bool:
        return self.log_level.upper() == "DEBUG"

    def print(self):
        """Prints the current configuration."""
        print("Current Configuration:")
        for key, value in self.__dict__.items():
            if key != "initialized":
                print(f"{key}: {value}")


def write_config():
    """Save the current configuration to a JSON file."""
    json_data = ConfigApp().json()
    return write_json_to_file(ConfigApp().config_app_file, json_data)


def is_prod():
    return ConfigApp().is_prod()


def is_dev():
    return ConfigApp().is_dev()


def is_debug():
    return ConfigApp().is_debug()


def getLogger():
    return ConfigApp().logger


def getDisplayFile():
    return os.path.join(
        os.path.expanduser(ConfigApp().log_dir), ConfigApp().display_file
    )


def getBatteryFile():
    return os.path.join(
        os.path.expanduser(ConfigApp().log_dir), ConfigApp().battery_file
    )


def getUhubctl():
    return ConfigApp().uhubctl


def getUsbDir():
    return ConfigApp().usb_dir


def getImageDir():
    return ConfigApp().image_dir


def getConfigHubFile():
    return os.path.join(
        os.path.expanduser(ConfigApp().config_dir), ConfigApp().config_hub_file
    )


def getConfigDir():
    return os.path.expanduser(ConfigApp().config_dir)


def getS3Bucket():
    return ConfigApp().s3_bucket


def getScanorhizeServer():
    return ConfigApp().scanorhize_server


def getConfigFile():
    return ConfigApp().config_app_file


def getLogDir():
    return ConfigApp().log_dir


def getThumbWidth():
    return ConfigApp().th_x


def getThumbHeight():
    return ConfigApp().th_y


if __name__ == "__main__":
    ConfigApp().print()
    print(f"Dev: {is_dev()}")
    print(f"Debug: {is_debug()}")
    getLogger().info("getLogger warning test")
    ConfigApp().save_config()
