# miscellious functions
from Scanner import *
import RPi.GPIO as GPIO

# miscellious functions

Ch1Pin = 19 #Scanner1
Ch2Pin = 26 #Scanner2
Ch3Pin = 20 #Scanner3
Ch4Pin = 21 #Clé 4G
GPIOList = [
    (Ch1Pin, "Scanner 1"),
    (Ch2Pin, "Scanner 2"),
    (Ch3Pin, "Scanner 3"),
    (Ch4Pin, "Clé 4G")
    ]

def InfoGPIO():
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        print("States :")
        for port in GPIOList:
            GPIO.setup(port[0], GPIO.OUT)
            print(f"  {port[1]}: {'off' if GPIO.input(port[0]) else 'on'}")
    except Exception as e:
        print(f"Exception {e}")
        return 1
    return 0

def manageGPIO():
    value = input("Voulez-vous modifier l'état des GPIO ? [Non=Entrée, sinon, Oui=o]: ")
    if not value:
        return 0
    # On va definir l'état des ports 1 par 1
    try:
        for port in GPIOList:
            value = input("Basculer " + port[1] + "? [Non=Entrée, sinon, Oui=o]: ")
            if value:
                GPIO.setup(port[0], GPIO.OUT)
                GPIO.output(port[0], not GPIO.input(port[0]))
                print(f"  bascule {port[1]}")
    except Exception as e:
        print(f"Exception {e}")
        return 2
    return 1


if __name__ == "__main__":
    InfoGPIO()
    if manageGPIO():
        InfoGPIO()
