from time import sleep
import smbus

WITTY_PI_I2C_ADDRESS = 0x69


class WittyPi:
    """Classe pour la carte Witty Pi qui permet de gérer l'alimentation du Raspberry Pi
    via un circuit intégré I2C
    Cette classe ne gère pas l'horloge RTC de la carte Witty Pi
    """

    def __init__(self):

        self.i2c_bus = smbus.SMBus(1)

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

            data = self.i2c_bus.read_byte_data(WITTY_PI_I2C_ADDRESS, register)

        except OSError as e:
            print(f"Read error: {e}")
            data = None

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


def main():

    witty_pi = WittyPi()
    print(witty_pi)

    for i in range(0, 5000):
        witty_pi.get_output_current()
        print(f"{i}:{witty_pi.output_current:.3f}", flush=True)
        sleep(1)


if __name__ == "__main__":

    main()
