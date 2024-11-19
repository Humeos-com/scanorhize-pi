# miscellious functions
from Scanner import *
import RPi.GPIO as GPIO

Ch1Pin = 19 #Scanner1
Ch2Pin = 26 #Scanner2
Ch3Pin = 20 #Scanner3
Ch4Pin = 21 #Scanner4
PinArray =[Ch1Pin,Ch2Pin,Ch3Pin,Ch4Pin]


def downGPIO():
    try:
        GPIO.setwarnings(False)       
        GPIO.setmode(GPIO.BCM) 
        print("States :")
        for scan_num, pin in enumerate(PinArray):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            print(f"  Scanner{scan_num+1}: {'off' if GPIO.input(pin) else 'on'}")
    except Exception as e:
        print(f"Exception {e}")
        return 1
    return 0

if __name__ == "__main__":
    retval = downGPIO()
