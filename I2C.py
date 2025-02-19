"""Lecture de l'état de la batterie via I2C"""

from OSUtils import is_raspberry_pi
from Miscellaneous import WriteBatterieFile

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

bus = SMBus(1)  # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)
DEVICE_ADDRESS = 0x55  # 7 bit address (will be left shifted to add the read write bit)


def ReadBatVoltCap():
    try:
        res = bus.read_i2c_block_data(DEVICE_ADDRESS, 0x04, 2)
        Volt = (res[1] * 256 + res[0]) / 1000
        Cap = round((Volt - 2.7) / 1.49 * 100, 2)
    except IOError:
        Volt = 0
        Cap = 0
    WriteBatterieFile(Volt, Cap)
    return (Volt, Cap)


def ReadBatSOC():
    try:
        res = bus.read_i2c_block_data(DEVICE_ADDRESS, 0x1C, 2)
        SOC = res[1] * 256 + res[0]
        print(SOC)
    except IOError:
        SOC = 0
    return SOC


def ReadBatCAP():
    try:
        res = bus.read_i2c_block_data(DEVICE_ADDRESS, 0x0A, 2)
        CAP = res[1] * 256 + res[0]
        print(CAP)
    except IOError:
        CAP = 0
    return CAP


if __name__ == "__main__":
    print(ReadBatCAP())
