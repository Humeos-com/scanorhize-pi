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
    import fake_rpi

    sys.modules["smbus"] = fake_rpi.smbus
    from smbus import SMBus

WITTY_PI_3_I2C_ADDRESS = 0x69
WITTY_PI_4_I2C_ADDRESS = 0x8
WITTY_PI_4_L3V7_FIRMWARE_ID = 0x37  # 55 en décimal
WITTY_PI_4_REASON_CLICK = 0x03

I2C_CONF_RECOVERY_VOLTAGE = 22
I2C_CONF_OVER_TEMP_ACTION = 45
I2C_CONF_OVER_TEMP_POINT = 46
I2C_LM75B_TOS = 53


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
                getLogger().error("ERROR: I2C bus not available")
                self.initialized = True
                return
            self.i2c_address = WITTY_PI_3_I2C_ADDRESS
            self.firmware_id = 0
            self.input_voltage = 0.0
            self.output_voltage = 0.0
            self.output_current = 0.0
            self.temperature = 0.0
            self.power_mode = 0
            self.firmware_revision = 0
            self.reason_click = 0
            self.auto_on = 0
            self.shutdown_temperature = 0
            self.next_shutdown_time = 0
            self.next_startup_time = 0

            # On commence par récupérer le type Witty Pi
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
            self.get_auto_on()
            self.get_shutdown_temperature()
            self.get_next_shutdown_time()
            self.get_next_startup_time()
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

    def get_auto_on(self):
        if self.firmware_id is None or self.firmware_id != WITTY_PI_4_L3V7_FIRMWARE_ID:
            return 0
        self.auto_on = self.read_register(I2C_CONF_RECOVERY_VOLTAGE)
        if self.auto_on is None or self.auto_on == 0:
            return 0
        self.auto_on = 1
        return self.auto_on

    def set_auto_on(self, auto_on):
        if self.firmware_id is None or self.firmware_id != WITTY_PI_4_L3V7_FIRMWARE_ID:
            return
        self.write_register(I2C_CONF_RECOVERY_VOLTAGE, auto_on)
        self.auto_on = auto_on
        return self.auto_on

    def get_shutdown_temperature(self):
        if self.firmware_id is None or self.firmware_id != WITTY_PI_4_L3V7_FIRMWARE_ID:
            return 0
        action = self.read_register(I2C_CONF_OVER_TEMP_ACTION)
        if action is None or action == 0:
            return "No action"
        if action == 1:
            # shutdown
            temp = self.read_register(I2C_LM75B_TOS)
            if temp > 127:
                temp = temp - 256
            self.shutdown_temperature = temp
        return self.shutdown_temperature

    def set_shutdown_temperature(self, shutdown_temperature):
        if self.firmware_id is None or self.firmware_id != WITTY_PI_4_L3V7_FIRMWARE_ID:
            return 0
        self.write_register(I2C_CONF_OVER_TEMP_ACTION, 1)
        self.write_register(I2C_LM75B_TOS, shutdown_temperature)
        self.shutdown_temperature = shutdown_temperature
        return self.shutdown_temperature

    def get_next_shutdown_time(self):
        if self.i2c_bus is None or self.firmware_id is None:
            return 0
        self.next_shutdown_time = self.read_register(15)
        return self.next_shutdown_time

    def get_next_startup_time(self):
        if self.i2c_bus is None or self.firmware_id is None:
            return 0
        self.next_startup_time = self.read_register(16)
        return self.next_startup_time

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

    def write_register(self, register, data):
        try:
            self.i2c_bus.write_byte_data(self.i2c_address, register, data)
            return True
        except OSError as e:
            msg = f"write_register: Write error: {e}"
            getLogger().error(msg)
            return False

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


def get_auto_on():

    return WittyPi().get_auto_on()


def get_shutdown_temperature():

    return WittyPi().get_shutdown_temperature()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="WittyPython.py",
        usage="%(prog)s [--version]",
        epilog="""Affiche les informations sur la carte Witty Pi""",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Affiche la version du programme",
    )
    parser.add_argument(
        "-P",
        "--poweron",
        action="store_true",
        help="Set auto-start on power on (default: False)",
    )
    parser.add_argument(
        "-T",
        "--temperature",
        type=int,
        help="Set shutdown temperature (default: 70°C)",
    )

    args = parser.parse_args()
    if args.version:
        print(f"WittyPython.py version: {__version__}")
        sys.exit(0)

    print(WittyPi())
    print(f"is_WittyPi_4_L3V7: {is_WittyPi_4_L3V7()}")
    print(ReadTemp())
    print(f"auto_on: {get_auto_on()}")
    print(f"shutdown_temperature: {get_shutdown_temperature()}")
    if args.poweron:
        WittyPi().set_auto_on(0)
        print(f"auto_on: {get_auto_on()}")
    if args.temperature:
        WittyPi().set_shutdown_temperature(args.temperature)
        print(f"shutdown_temperature: {get_shutdown_temperature()}")

    # for i in range(0, 5000)
    for i in range(0, 1):
        print(f"{i}:{WittyPi().get_output_current():.3f}", flush=True)
        sleep(1)
