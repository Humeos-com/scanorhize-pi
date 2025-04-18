"""
Permet de gérer l'environnement matériel OS, cartes, etc.
Utilise le pattern Singleton pour stocker la configuration
"""

import os
import json
import logging
import logging.config
from datetime import datetime


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
            self.log_level = "DEBUG"
        else:
            self.config_app_file = f"{CONFIG_APP_FILE}-prod.json"

        if os.path.exists("DEBUG") or os.environ.get("DEBUG", False):
            self.log_level = "DEBUG"

        # Type hints for required attributes
        self.config_app_file: str
        self.log_level: str = "INFO"
        self.log_dir: str = "Log"
        self.config_dir: str = "ConfigFile"
        self.next_date_file: str = "NextStartDate.json"
        self.config_hub_file: str = "Hub.json"
        self.display_file: str = "Display.txt"
        self.battery_file: str = "Battery.txt"
        self.uhubctl: str = "/usr/sbin/uhubctl"
        self.usb_dir: str = "/media/pi/Image"
        self.image_dir: str = "static"
        self.s3_bucket: str = "s3://scanorhize-images-prod"
        self.scanorhize_server: str = "scanorhize.duckdns.org"
        self.connect_timeout: int = 10
        self.max_time: int = 300
        # Pour le relai Banggood initial
        # pins BCM
        # Ch1Pin = 19  # Scanner1
        # Ch2Pin = 26  # Scanner2
        # Ch3Pin = 20  # Scanner3
        # Ch4Pin = 21  # Clé 4G

        # Pour le relai SBComponent RelayPi-V2
        # pins BCM
        # Ch1Pin = 19  # Scanner1
        # Ch2Pin = 13  # Scanner2
        # Attention pour ces 2 pins, il faut supprimer les jumpers jaunes
        # et cabler GPIO 27 et 22 (board pins 13 et 15) sur les relais avec des cables Dupont
        # Ch3Pin = 22  # Scanner3
        # Ch4Pin = 27  # Clé 4G

        # Pour l'alimentation de la carte WittyPi L3V7
        # Pour les explications, voir le programme wittyPi.sh fourni par UUGEAR
        # Pins BCM
        # CHRG_PIN = 5  # input to detect charging status
        # STDBY_PIN = 6  # input to detect standby status
        # Pour la carte USB Big 7
        self.Ch1Pin: int # Scanner1
        self.Ch2Pin: int # Scanner2
        self.Ch3Pin: int # Scanner3
        self.Ch4Pin: int # clé 4G
        self.PinArray = []

        # Initialize logger
        self.logger = logging.getLogger("ConfigApp")

        # Setup logging and load config
        self.setup_basic_logging()
        self.load_config()
        self.setup_final_logging()

        self.initialized = True  # Mark as initialized
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
        logging_conf = os.path.join(self.config_dir, "logging.conf")
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
        """Load config and update attributes dynamically"""
        if not os.path.exists(self.config_app_file):
            self.logger.error("No file: %s", self.config_app_file)
            return self

        try:
            with open(self.config_app_file, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)
                # Update attributes from JSON, including any new ones
                for key, value in data.items():
                    if key != "logger":  # Skip logger to maintain logging setup
                        setattr(self, key, value)
        except (FileNotFoundError, ValueError):
            self.logger.error("Problem with config file: %s", self.config_app_file)

        if self.log_level.upper() == "DEBUG":
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        self.PinArray = [self.Ch1Pin, self.Ch2Pin, self.Ch3Pin, self.Ch4Pin]

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
        try:
            with open(self.config_app_file, "w", encoding="utf-8") as outfile:
                outfile.write(json_data)
                return 0
        except OSError as e:
            getLogger().error("save_config: OSError: %s", e)
            return 1

    def is_prod(self) -> bool:
        """Returns True if environment is set to PROD."""
        return self.environment.upper() == "PROD"

    def is_dev(self) -> bool:
        """Returns True if environment is set to DEV."""
        return self.environment.upper() == "DEV"

    def is_debug(self) -> bool:
        return self.log_level.upper() == "DEBUG"

    def getChPin(self, i_scan: int):
        if 0 <= i_scan < 4:
            return self.PinArray[i_scan]
        self.logger.error(
            "La valeur passee doit être comprise entre 0 et 4, ici: %d", i_scan
        )
        return -1

    def print(self):
        """Prints the current configuration."""
        print("Current Configuration:")
        for key, value in self.__dict__.items():
            if key != "initialized":
                print(f"{key}: {value}")


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


def getNextDateFile():
    return os.path.join(
        os.path.expanduser(ConfigApp().config_dir), ConfigApp().next_date_file
    )


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


def getConnectTimeout():
    return ConfigApp().connect_timeout


def getMaxTime():
    return ConfigApp().max_time


def getConfigFile():
    return ConfigApp().config_app_file


def getLogDir():
    return ConfigApp().log_dir


def getChPin(i_scan: int):
    return ConfigApp().getChPin(i_scan)


if __name__ == "__main__":
    ConfigApp().print()
    print(f"Dev: {is_dev()}")
    print(f"Debug: {is_debug()}")
    getLogger().warning("getLogger warning test")
    ConfigApp().save_config()
