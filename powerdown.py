"""Eteint tous les 3 ports USB des scanners"""

from OSUtils import is_raspberry_pi

# pylint: disable=ungrouped-imports
# pylint: disable=import-error
# Impossible de grouper les imports car les imports conditionnels ne sont pas supportés
if is_raspberry_pi():
    from RPi import GPIO
else:
    import sys
    import fake_rpi

    sys.modules["RPi"] = fake_rpi.RPi  # Mock RPi module
    sys.modules["RPi.GPIO"] = fake_rpi.RPi.GPIO
    sys.modules["smbus"] = fake_rpi.smbus
    from RPi import GPIO

Ch1Pin = 19  # Scanner1
Ch2Pin = 26  # Scanner2
Ch3Pin = 20  # Scanner3
# Ch4Pin = 21 #Clé 4G
PinArray = [Ch1Pin, Ch2Pin, Ch3Pin]


def downGPIO():
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        print("States :")
        for scan_num, pin in enumerate(PinArray):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            print(f"  Scanner{scan_num+1}: {'off' if GPIO.input(pin) else 'on'}")
    except IOError as e:
        print(f"Exception {e}")
        return 1
    return 0


if __name__ == "__main__":
    retval = downGPIO()
