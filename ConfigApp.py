"""
Permet de gérer l'environnement matériel OS, cartes, etc.
Utilise le pattern Singleton pour stocker la configuration
"""

import os
from dataclasses import dataclass, asdict
import json
import logging
import logging.config
from datetime import datetime


# CONFIG_PATH = "ConfigFile/Scanner"
CONFIG_APP_FILE = "~/scanorhize.json"


@dataclass
class ConfigApp:
    """Class to hold configuration data"""

    _instance = None  # Class variable to store the single instance
    config_app_file = os.path.expanduser(CONFIG_APP_FILE)
    environment: str = "PROD"
    log_level: str = "INFO"
    log_dir: str = "Log"
    config_path: str = "ConfigFile"
    next_date_file: str = "NextStartDate.json"
    config_hub_file: str = "Hub.json"
    display_file: str = "Log/Display.txt"
    battery_file: str = "Log/Battery.txt"
    uhubctl: str = "/usr/sbin/uhubctl"
    usb_dir: str = "/media/pi/Image"
    scanorhize_server: str = "scanorhize.duckdns.org"
    connect_timeout: int = 10
    max_time: int = 300

    # Start to setup formatter
    logging_conf = os.path.join(config_path, "logging.conf")
    if os.path.exists(logging_conf):
        logging.config.fileConfig(logging_conf)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(lineno)04d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    logger = logging.getLogger("MainLogger")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigApp, cls).__new__(cls)
            cls._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):
        """Load config from environment variables or config.json"""

        # Setup logging dans un fichier avec timestamp
        log_file = os.path.join(
            os.path.expanduser(cls._instance.log_dir),
            f"Scanorhize_{datetime.now():%Y-%m-%d}.log",
        )
        fh = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(lineno)04d | %(message)s"
        )
        formatter.default_msec_format = None
        fh.setFormatter(formatter)
        cls._instance.logger.addHandler(fh)

        if not os.path.exists(cls._instance.config_app_file):
            cls._instance.logger.error("No file: %s", cls._instance.config_app_file)
            return cls

        try:
            with open(cls._instance.config_app_file, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)
                # Use setattr instead of updating __dict__
                for key, value in data.items():
                    setattr(cls._instance, key, value)
        except (FileNotFoundError, ValueError):
            cls._instance.logger.error(
                "Problem with the config file: %s", cls._instance.config_app_file
            )

        # Environment overrides
        if os.path.exists("DEV") or os.environ.get("DEV", False):
            cls._instance.environment = "DEV"
        if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
            cls._instance.log_level = "DEBUG"

        # Environment variables override
        cls._instance.environment = os.getenv("APP_ENV", cls._instance.environment)
        cls._instance.log_level = os.getenv("LOG_LEVEL", cls._instance.log_level)
        if cls.log_level.upper() == "DEBUG":
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        cls._instance.logger.warning(
            "Read configuration from: %s", cls._instance.config_app_file
        )
        return cls

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

    def print(self):
        for name, value in asdict(self).items():
            print(f"{name}: {value}")


def is_dev():
    return ConfigApp().is_dev()


def is_debug():
    return ConfigApp().is_debug()


def WriteTimeLogfile(data):
    ConfigApp().logger.warning("%s", data)


def getLogger():
    return ConfigApp().logger


def getDisplayFile():
    return ConfigApp().display_file


def getBatteryFile():
    return ConfigApp().battery_file


def getUhubctl():
    return ConfigApp().uhubctl


def getUsbDir():
    return ConfigApp().usb_dir


def getNextDateFile():
    return os.path.join(
        os.path.expanduser(ConfigApp().config_path), ConfigApp().next_date_file
    )


def getConfigHubFile():
    return os.path.join(
        os.path.expanduser(ConfigApp().config_path), ConfigApp().config_hub_file
    )


def getConfigPath():
    return os.path.expanduser(ConfigApp().config_path)


def getScanorhizeServer():
    return ConfigApp().scanorhize_server


def getConnectTimeout():
    return ConfigApp().connect_timeout


def getMaxTime():
    return ConfigApp().max_time


def getConfigFile():
    return ConfigApp().config_app_file


def getLogDir():
    return ConfigApp().log_dir


if __name__ == "__main__":
    ConfigApp().print()
    print(f"Dev: {is_dev()}")
    print(f"Debug: {is_debug()}")
    WriteTimeLogfile("WriteTimeLogfile test")
