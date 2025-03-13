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

    _instance = None  # Class variable to store the single instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WittyPi, cls).__new__(cls)
            # cls._load_config()
        return cls._instance

    # pylint: disable=too-many-instance-attributes
    @classmethod
    def __init__(cls):

        cls.i2c_bus = SMBus(1)
        cls.i2c_address = WITTY_PI_3_I2C_ADDRESS

        cls.firmware_id = 0
        cls.input_voltage = 0.0
        cls.output_voltage = 0.0
        cls.output_current = 0.0
        cls.temperature = 0.0
        cls.power_mode = 0
        cls.firmware_revision = 0

        cls.get_firmware_id()
        cls.get_input_voltage()
        cls.get_output_voltage()
        cls.get_output_current()
        cls.get_temperature()
        cls.get_power_mode()
        cls.get_firmware_revision()

    @classmethod
    def get_firmware_id(cls):

        cls.firmware_id = cls.read_register(0x00)
        if cls.firmware_id is None:
            print(f"No Witty Pi board on address 0x{cls.i2c_address:02X}")
            cls.i2c_address = WITTY_PI_4_I2C_ADDRESS
        cls.firmware_id = cls.read_register(0x00)
        if cls.firmware_id is None:
            print("Aucune carte Witty Py trouvee.")
        return cls.firmware_id

    @classmethod
    def get_input_voltage(cls):

        cls.input_voltage = cls.read_register(0x01) + cls.read_register(0x02) / 100
        return cls.input_voltage

    @classmethod
    def get_output_voltage(cls):

        cls.output_voltage = cls.read_register(0x03) + cls.read_register(0x04) / 100
        return cls.output_voltage

    @classmethod
    def get_output_current(cls):

        cls.output_current = cls.read_register(0x05) + cls.read_register(0x06) / 100
        return cls.output_current

    @classmethod
    def get_power_mode(cls):

        cls.power_mode = cls.read_register(0x07)
        return cls.power_mode

    @classmethod
    def get_temperature(cls):

        data = cls.read_register(50, 2)
        # Step 1: Swap bytes
        data = (((data & 0xFF) << 8) | ((data & 0xFF00) >> 8)) >> 5
        # Step 2: Two's complement correction (if data >= 1024)
        if data >= 0x400:
            data = (data & 0x3FF) - 1024  # Convert to negative if needed
        # Step 3: Scale by 0.125
        data = data * 0.125
        cls.temperature = data
        return cls.temperature

    @classmethod
    def get_firmware_revision(cls):

        cls.firmware_revision = cls.read_register(12)
        return cls.firmware_revision

    @classmethod
    def read_register(cls, register, len_=1):

        try:

            if len_ == 1:
                data = cls.i2c_bus.read_byte_data(cls.i2c_address, register)
            else:
                data = cls.i2c_bus.read_word_data(cls.i2c_address, register)

        except OSError as e:
            print(f"Read error: {e}")
            return None

        return data

    @classmethod
    def is_WittyPi_3(cls):

        return cls.i2c_address == WITTY_PI_3_I2C_ADDRESS

    @classmethod
    def is_WittyPi_4(cls):

        return cls.i2c_address == WITTY_PI_4_I2C_ADDRESS

    @classmethod
    def __str__(cls):

        s = ("Witty Pi\n"
        f"  Firmware ID: {cls.firmware_id:02X}\n"
        f"  Firmware revision: {cls.firmware_revision}\n"
        f"  Input voltage: {cls.input_voltage:.3f}V\n"
        f"  Output voltage: {cls.output_voltage:.3f}V\n"
        f"  Output current: {cls.output_current:.3f}A\n"
        "  Power mode: "
        + ("LDO regulator" if cls.power_mode == 1 else "5V USB")
        + "\n"
        f"  Temperature: {cls.temperature:.1f}C")

        return s

def is_WittyPi_3():

    return WittyPi().is_WittyPi_3()

def is_WittyPi_4():

    return WittyPi().is_WittyPi_4()


def main():

    print(WittyPi())
    print(f"Is WittyPi 3: {is_WittyPi_3()}")
    print(f"Is WittyPi 4: {is_WittyPi_4()}")

    for i in range(0, 5000):
        print(f"{i}:{WittyPi().get_output_current():.3f}", flush=True)
        sleep(1)


if __name__ == "__main__":

    main()
