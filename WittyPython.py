"""Interroge la carte Witty Pi pour obtenir des informations sur l'alimentation
de la carte Raspberry Pi
"""

from time import sleep
from logging import getLogger
import argparse
import sys
from OSUtils import is_raspberry_pi
from version import __version__


# pylint: disable=ungrouped-imports
# pylint: disable=import-error
# Impossible de grouper les imports car les imports conditionnels ne sont pas supportés
if is_raspberry_pi():
    from smbus import SMBus
else:
    import sys
    import fake_rpi

    sys.modules["smbus"] = fake_rpi.smbus
    from smbus import SMBus

WITTY_PI_3_I2C_ADDRESS = 0x69
WITTY_PI_4_I2C_ADDRESS = 0x8
WITTY_PI_4_L3V7_FIRMWARE_ID = 0x37  # 55 en décimal
WITTY_PI_4_REASON_CLICK = 0x03


class WittyPi:
    """Classe pour la carte Witty Pi qui permet de gérer l'alimentation du Raspberry Pi
    via un circuit intégré I2C
    Cette classe ne gère pas l'horloge RTC de la carte Witty Pi
    """

    _instance = None  # Class variable to store the single instance

    def __new__(cls):
        """Ensure only one instance is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(WittyPi, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the instance if not already initialized."""
        if not hasattr(self, "initialized"):  # Prevent re-initialization
            try:
                self.i2c_bus = SMBus(1)
            except FileNotFoundError:
                self.i2c_bus = None
                getLogger().error("I2C bus not available")
            self.i2c_address = WITTY_PI_3_I2C_ADDRESS
            self.firmware_id = 0
            self.input_voltage = 0.0
            self.output_voltage = 0.0
            self.output_current = 0.0
            self.temperature = 0.0
            self.power_mode = 0
            self.firmware_revision = 0
            self.reason_click = 0

            self.get_firmware_id()
            if self.firmware_id is None:
                self.initialized = True
                return
            self.get_power_mode()
            self.get_input_voltage()
            self.get_output_voltage()
            self.get_output_current()
            self.get_temperature()
            self.get_firmware_revision()
            self.get_reason_click()

            self.initialized = True  # Mark as initialized

    def get_firmware_id(self):

        self.firmware_id = self.read_register(0x00)
        if self.firmware_id is None:
            msg = f"No Witty Pi board on address 0x{self.i2c_address:02X}"
            getLogger().warning(msg)
            self.i2c_address = WITTY_PI_4_I2C_ADDRESS
        self.firmware_id = self.read_register(0x00)
        if self.firmware_id is None:
            getLogger().error("Aucune carte Witty Py trouvee.")
        return self.firmware_id

    def get_input_voltage(self):

        if self.i2c_bus is None or self.firmware_id is None:
            return 0.0
        if self.get_power_mode() != 0:
            reg_01 = self.read_register(0x01)
            reg_02 = self.read_register(0x02)
            if reg_01 is None or reg_02 is None:
                self.input_voltage = 0.0
            self.input_voltage = reg_01 + reg_02 / 100
        else:
            self.input_voltage = 0.0
        return self.input_voltage

    def get_output_voltage(self):

        if self.i2c_bus is None or self.firmware_id is None:
            return 0.0
        reg_03 = self.read_register(0x03)
        reg_04 = self.read_register(0x04)
        if reg_03 is None or reg_04 is None:
            return 0.0
        self.output_voltage = self.read_register(0x03) + self.read_register(0x04) / 100
        return self.output_voltage

    def get_output_current(self):

        if self.i2c_bus is None or self.firmware_id is None:
            return 0.0
        reg_05 = self.read_register(0x05)
        reg_06 = self.read_register(0x06)
        if reg_05 is None or reg_06 is None:
            return 0.0
        self.output_current = reg_05 + reg_06 / 100
        return self.output_current

    def get_power_mode(self):

        if self.i2c_bus is None or self.firmware_id is None:
            return 0
        self.power_mode = self.read_register(0x07)
        return self.power_mode

    def get_temperature(self):

        if self.i2c_bus is None or self.firmware_id is None:
            return 0.0
        data = self.read_register(50, 2)
        # Step 1: Swap bytes
        data = (((data & 0xFF) << 8) | ((data & 0xFF00) >> 8)) >> 5
        # Step 2: Two's complement correction (if data >= 1024)
        if data >= 0x400:
            data = (data & 0x3FF) - 1024  # Convert to negative if needed
        # Step 3: Scale by 0.125
        self.temperature = data * 0.125
        return self.temperature

    def get_firmware_revision(self):
        if self.i2c_bus is None or self.firmware_id is None:
            return 0
        self.firmware_revision = self.read_register(12)
        return self.firmware_revision

    def get_reason_click(self):
        if self.i2c_bus is None or self.firmware_id is None:
            return 0
        self.reason_click = self.read_register(11)
        return self.reason_click

    def read_register(self, register, len_=1):

        try:

            if len_ == 1:
                data = self.i2c_bus.read_byte_data(self.i2c_address, register)
            else:
                data = self.i2c_bus.read_word_data(self.i2c_address, register)

        except OSError as e:
            msg = f"read_register: Read error: {e}"
            getLogger().error(msg)
            return None

        return data

    def is_WittyPi_3(self):
        if self.i2c_bus is None or self.firmware_id is None:
            return False
        try:
            return self.i2c_bus.read_byte_data(0x69, 0x00) == 0x11
        except (OSError, IOError) as e:
            getLogger().warning("Error reading WittyPi: %s", e)
            return False

    def is_WittyPi_4(self):

        return self.i2c_address == WITTY_PI_4_I2C_ADDRESS

    def is_WittyPi_4_L3V7(self):

        return self.firmware_id == WITTY_PI_4_L3V7_FIRMWARE_ID

    def is_reason_click(self):
        if self.i2c_bus is None or self.firmware_id is None:
            return False
        return self.reason_click == WITTY_PI_4_REASON_CLICK

    def __str__(self):

        if self.firmware_id is None:
            return "  Pas de carte WittyPi !\n"
        if self.is_WittyPi_3():
            s = "  Carte WittyPi: 3\n"
        else:
            if self.is_WittyPi_4():
                s = "  Carte WittyPi: 4\n"
            else:
                return "  Pas de carte WittyPi !\n"

        s += (
            f"  Firmware ID: {self.firmware_id:02X}\n"
            f"  Firmware revision: {self.firmware_revision}\n"
            f"  Input voltage: {self.input_voltage:.3f}V\n"
            f"  Output voltage: {self.output_voltage:.3f}V\n"
            f"  Output current: {self.output_current:.3f}A\n"
            f"  Power mode: {'LDO regulator' if self.power_mode == 1 else '5V USB'}\n"
            f"  Temperature: {self.temperature:.1f}C"
        )

        return s


def is_WittyPi_3():

    return WittyPi().is_WittyPi_3()


def is_WittyPi_4():

    return WittyPi().is_WittyPi_4()


def is_WittyPi_4_L3V7():

    return WittyPi().is_WittyPi_4_L3V7()


def get_input_voltage():

    return WittyPi().get_input_voltage()


def get_output_voltage():

    return WittyPi().get_output_voltage()


def get_output_current():

    return WittyPi().get_output_current()


def get_power_mode():

    return WittyPi().get_power_mode()


def ReadTemp():

    return WittyPi().get_temperature()


def is_reason_click():

    return WittyPi().is_reason_click()


def main():

    print(WittyPi())
    print(f"is_WittyPi_4_L3V7: {is_WittyPi_4_L3V7()}")
    print(ReadTemp())

    # for i in range(0, 5000):
    for i in range(0, 1):
        print(f"{i}:{WittyPi().get_output_current():.3f}", flush=True)
        sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="WittyPython.py",
        usage="%(prog)s [--version]",
        epilog="""Affiche les informations sur la carte Witty Pi""",
    )
    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Affiche la version du programme",
    )

    args = parser.parse_args()
    if args.version:
        print(f"WittyPython.py version: {__version__}")
        sys.exit(0)

    main()
