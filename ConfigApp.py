"""
Permet de gérer l'environnement matériel OS, cartes, etc.
Utilise le pattern Singleton pour stocker la configuration
"""

import os
import json
import logging
import logging.config
from datetime import datetime


# CONFIG_PATH = "ConfigFile/Scanner"
# Path to the config file
CONFIG_APP_FILE = os.path.expanduser("~/scanorhize.json")


class ConfigApp:
    """Class to hold configuration data"""

    _instance = None  # Class variable to store the single instance

    config_app_file = CONFIG_APP_FILE
    environment: str
    log_level: str
    log_dir: str
    config_path: str
    next_date_file: str
    config_hub_file: str
    display_file: str
    battery_file: str
    uhubctl: str
    usb_dir: str
    scanorhize_server: str
    connect_timeout: int
    max_time: int
    logger: logging.Logger  # Define logger attribute

    def __new__(cls):
        """Ensure only one instance is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(ConfigApp, cls).__new__(cls)
            cls._instance._initialize()  # Initialize instance variables
        return cls._instance

    def _initialize(self):
        """Initialize default values (runs only once)."""
        self.environment = "PROD"
        self.log_level = "INFO"
        self.log_dir = "Log"
        self.config_path = "ConfigFile"
        self.next_date_file = "NextStartDate.json"
        self.config_hub_file = "Hub.json"
        self.display_file = "Log/Display.txt"
        self.battery_file = "Log/Battery.txt"
        self.uhubctl = "/usr/sbin/uhubctl"
        self.usb_dir = "/media/pi/Image"
        self.scanorhize_server = "scanorhize.duckdns.org"
        self.connect_timeout = 10
        self.logger = logging.getLogger("ConfigApp")

        # Setup basic logging with defaults
        self.setup_basic_logging()

        # Load configuration
        self.load_config()

        # Update logging with final config
        self.setup_final_logging()

        # Log the configuration load
        self.logger.warning("Read configuration from: %s", self.config_app_file)

    def setup_basic_logging(self):
        """Setup initial basic logging"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(lineno)04d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger("MainLogger")

    def setup_final_logging(self):
        """Setup final logging configuration"""
        # Clear existing handlers
        logging.getLogger().handlers.clear()

        # Check for logging.conf
        logging_conf = os.path.join(self.config_path, "logging.conf")
        if os.path.exists(logging_conf):
            logging.config.fileConfig(logging_conf)
            self.logger = logging.getLogger("MainLogger")
        # Remove existing FileHandler(s)
        for handler in self.logger.handlers[:]:
            if (
                isinstance(handler, logging.FileHandler)
                and handler.name == "fileHandler"
            ):
                self.logger.removeHandler(handler)
        # Setup file handler with timestamp
        log_file = os.path.join(
            os.path.expanduser(self.log_dir),
            f"Scanorhize_{datetime.now():%Y-%m-%d}.log",
        )
        fh = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(lineno)04d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Set final log level
        log_level = logging.DEBUG if self.log_level.upper() == "DEBUG" else logging.INFO
        self.logger.setLevel(log_level)

    def load_config(self):
        """Load config from environment variables or config.json"""

        # Clear existing handlers to avoid duplicate log lines
        self.logger.handlers.clear()

        if not os.path.exists(self.config_app_file):
            self.logger.error("No file: %s", self.config_app_file)
            return self

        try:
            with open(self.config_app_file, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)
                # Use setattr instead of updating __dict__
                for key, value in data.items():
                    setattr(self, key, value)
        except (FileNotFoundError, ValueError):
            self.logger.error("Problem with the config file: %s", self.config_app_file)

        # Environment overrides
        if os.path.exists("DEV") or os.environ.get("DEV", False):
            self.environment = "DEV"
        if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
            self.log_level = "DEBUG"

        # Environment variables override
        self.environment = os.getenv("APP_ENV", self.environment)
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        if self.log_level.upper() == "DEBUG":
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        self.logger.warning("Read configuration from: %s", self.config_app_file)
        return self

    def _setup_logging(self):
        """Configure logging based on environment"""
        log_level = logging.DEBUG if self.log_level.upper() == "DEBUG" else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info("Logging initialized at level: %s", self.log_level)

    def is_dev(self) -> bool:
        """Returns True if environment is set to DEV."""
        return self.environment.upper() == "DEV"

    def is_debug(self) -> bool:
        return self.log_level.upper() == "DEBUG"

    def print(self):
        """Prints the current configuration."""
        print("Current Configuration:")
        for key, value in self.__dict__.items():
            print(f"{key}: {value}")


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
    getLogger().warning("getLogger warning test")
    WriteTimeLogfile("WriteTimeLogfile test")
