"""Interroge la carte Witty Pi pour obtenir des informations sur l'alimentation
de la carte Raspberry Pi
"""

from time import sleep
from OSUtils import is_raspberry_pi

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


class WittyPi:
    """Classe pour la carte Witty Pi qui permet de gérer l'alimentation du Raspberry Pi
    via un circuit intégré I2C
    Cette classe ne gère pas l'horloge RTC de la carte Witty Pi
    """
    # pylint: disable=too-many-instance-attributes

    _instance = None  # Class variable to store the single instance

    def __new__(cls):
        """Ensure only one instance is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(WittyPi, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the instance if not already initialized."""
        if not hasattr(self, "initialized"):  # Prevent re-initialization
            self.i2c_bus = SMBus(1)
            self.i2c_address = WITTY_PI_3_I2C_ADDRESS
            self.firmware_id = 0
            self.input_voltage = 0.0
            self.output_voltage = 0.0
            self.output_current = 0.0
            self.temperature = 0.0
            self.power_mode = 0
            self.firmware_revision = 0

            self.get_firmware_id()
            self.get_input_voltage()
            self.get_output_voltage()
            self.get_output_current()
            self.get_temperature()
            self.get_power_mode()
            self.get_firmware_revision()

            self.initialized = True  # Mark as initialized

    def get_firmware_id(self):

        self.firmware_id = self.read_register(0x00)
        if self.firmware_id is None:
            print(f"No Witty Pi board on address 0x{self.i2c_address:02X}")
            self.i2c_address = WITTY_PI_4_I2C_ADDRESS
        self.firmware_id = self.read_register(0x00)
        if self.firmware_id is None:
            print("Aucune carte Witty Py trouvee.")
        return self.firmware_id

    def get_input_voltage(self):

        self.input_voltage = self.read_register(0x01) + self.read_register(0x02) / 100
        return self.input_voltage

    def get_output_voltage(self):

        self.output_voltage = self.read_register(0x03) + self.read_register(0x04) / 100
        return self.output_voltage

    def get_output_current(self):

        self.output_current = self.read_register(0x05) + self.read_register(0x06) / 100
        return self.output_current

    def get_power_mode(self):

        self.power_mode = self.read_register(0x07)
        return self.power_mode

    def get_temperature(self):

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

        self.firmware_revision = self.read_register(12)
        return self.firmware_revision

    def read_register(self, register, len_=1):

        try:

            if len_ == 1:
                data = self.i2c_bus.read_byte_data(self.i2c_address, register)
            else:
                data = self.i2c_bus.read_word_data(self.i2c_address, register)

        except OSError as e:
            print(f"Read error: {e}")
            return None

        return data

    def is_WittyPi_3(self):

        return self.i2c_address == WITTY_PI_3_I2C_ADDRESS

    def is_WittyPi_4(self):

        return self.i2c_address == WITTY_PI_4_I2C_ADDRESS

    def __str__(self):

        if self.is_WittyPi_3():
            s = "  Carte WittyPi: 3\n"
        else:
            if self.is_WittyPi_4():
                s = "  Carte WittyPi: 4\n"
            else:
                s = "  Pas de carte WittyPi !\n"
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

def ReadBatVoltCap():

    Volt = WittyPi().get_input_voltage()
    Cap = round((Volt - 2.7) / 1.49 * 100, 2)
    return (Volt, Cap)

def ReadTemp():

    return WittyPi().get_temperature()

def main():

    print(WittyPi())
    print(ReadBatVoltCap())
    print(ReadTemp())

    for i in range(0, 5000):
        print(f"{i}:{WittyPi().get_output_current():.3f}", flush=True)
        sleep(1)


if __name__ == "__main__":

    main()
