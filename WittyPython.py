from time import sleep
import smbus

WITTY_PI_3_I2C_ADDRESS = 0x69
WITTY_PI_4_I2C_ADDRESS = 0x8

class WittyPi:
    """Classe pour la carte Witty Pi qui permet de gérer l'alimentation du Raspberry Pi
    via un circuit intégré I2C
    Cette classe ne gère pas l'horloge RTC de la carte Witty Pi
    """

    def __init__(self):

        self.i2c_bus = smbus.SMBus(1)
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

    def get_firmware_id(self):

        self.firmware_id = self.read_register(0x00)
        if self.firmware_id is None:
            print(f"No Witty Pi board on address 0x{self.i2c_address:02X}")
            self.i2c_address = WITTY_PI_4_I2C_ADDRESS
        self.firmware_id = self.read_register(0x00)
        if self.firmware_id is None:
            print("Aucune carte Witty Py trouvee.")

    def get_input_voltage(self):

        self.input_voltage = self.read_register(0x01) + self.read_register(0x02) / 100

    def get_output_voltage(self):

        self.output_voltage = self.read_register(0x03) + self.read_register(0x04) / 100

    def get_output_current(self):

        self.output_current = self.read_register(0x05) + self.read_register(0x06) / 100

    def get_power_mode(self):

        self.power_mode = self.read_register(0x07)

    def get_temperature(self):

        self.temperature = self.read_register(0x07)


    def get_firmware_revision(self):

        self.firmware_revision = self.read_register(0x12)

    def read_register(self, register):

        try:

            data = self.i2c_bus.read_byte_data(self.i2c_address, register)

        except OSError as e:
            print(f"Read error: {e}")
            return None

        return data

    def __str__(self):

        s = "Witty Pi\n"

        s += f"  Firmware ID: {self.firmware_id:02X}\n"
        s += f"  Firmware revision: {self.firmware_revision}\n"
        s += f"  Input voltage: {self.input_voltage:.3f}V\n"
        s += f"  Output voltage: {self.output_voltage:.3f}V\n"
        s += f"  Output current: {self.output_current:.3f}A\n"
        s += (
            "  Power mode: "
            + ("LDO regulator" if self.power_mode == 1 else "5V USB")
            + "\n"
        )

        return s

def is_WittyPi_3():

    witty_pi = WittyPi()
    return witty_pi.i2c_address == WITTY_PI_3_I2C_ADDRESS 

def is_WittyPi_4():

    witty_pi = WittyPi()
    return witty_pi.i2c_address == WITTY_PI_4_I2C_ADDRESS 


def main():

    witty_pi = WittyPi()
    print(witty_pi)
    print(f"Is WittyPi 3: {is_WittyPi_3()}")
    print(f"Is WittyPi 4: {is_WittyPi_4()}")

    for i in range(0, 5000):
        witty_pi.get_output_current()
        print(f"{i}:{witty_pi.output_current:.3f}", flush=True)
        sleep(1)


if __name__ == "__main__":

    main()
