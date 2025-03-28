"""Lance le scanner et programme le prochain réveil"""

import sys
from subprocess import run, CalledProcessError

from WittyPy import SetNextStartDate, doShutdown, setNextShutdownDate
from WittyPython import ReadBatVoltCap, ReadTemp
from Miscellaneous import (
    InitGPIO,
    EndGPIO,
    TurnUsbOn,
    ReadGPIOConfig,
)
from DateUtils import GetCurrentDate, SecondsToDate, DateToSeconds, CalculNextStartDate
from ConfigApp import is_dev, getLogger
from Scanner import listConfigScanner, ScannerData
from Server import HubData, SendParameters
from Campaign import USBSpace



getLogger().warning("ScanorhizeStart.py")

res = InitGPIO()
if res != 0:
    getLogger().error("InitGPIOError")
# On allume la clé 4G
res = TurnUsbOn(3, 0)
if res != 0:
    getLogger().error("TurnUsbOnError")


config = ReadGPIOConfig()
EndGPIO()

# connexion réseau en parralèle pour optimiser le temps
# res=0
# iteration=0
# while res==0 and iteration<12:
# res=pingAPI("www.google.com")
# if res==0:
#   cmd="sudo ifconfig wlan0 down"
#  WriteTimeLogfile(cmd)
# subprocess.call(cmd,shell=True)
# cmd="sudo ifconfig wlan0 up"
# WriteTimeLogfile(cmd)
# subprocess.call(cmd,shell=True)
# sleep(20)
# WriteTimeLogfile(str(res)+" "+str(iteration))
# iteration=iteration+1


if config == 0:
    # En mode config
    cmd = "sudo python3 Scanorhize.py &"
    getLogger().warning(cmd)
    run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    sys.exit(0)

# Etape 1 #############################################
# Mise à jour des dates de réveil et d'arrêt du WittyPi
DateStart = GetCurrentDate()
CurrentDateinS = DateToSeconds(DateStart)

# On détermine la prochaine date de réveil à partir du fichier NextStartDate.json
NextStartseconds = [0, 0, 0]
NextStartDates = [" ", " ", " "]


# A mettre à jour avec les données des scanners
Scanner = ScannerData()
listScannerconfigs = listConfigScanner()
i_scan = 0
for CurrentScanner in listScannerconfigs:
    Scanner.ReadScannerConfig(CurrentScanner)
    DateOriginS = DateToSeconds(Scanner.StartDate)
    nextDate, nextDateS = CalculNextStartDate(
        Scanner.StartDate, Scanner.PeriodeS, DateStart
    )
    NextStartDates[i_scan] = nextDate
    NextStartseconds[i_scan] = nextDateS
    getLogger().warning("Scanner-%s: Next start date: %s", i_scan+1, nextDate)
    i_scan += 1

# Quand la carte WittyPi n'a plus de batterie, son heure interne est aléatoire.
# Lorsque les acquisitions ne fonctionnent pas, la nextStartDate ne bouge pas.
# Donc elle se retrouve dans le passé. Avec un minimum de secs_now + 600, on
# espère que la carte WittyPi se réveillera.
nextStartSecs = max(int(min(NextStartseconds)), (CurrentDateinS + 600))
nextStartDateValue = SecondsToDate(nextStartSecs)
getLogger().warning("Next start at: %s", nextStartDateValue)

Bat = ReadBatVoltCap()
if Bat[1] < 0:  # si plus de batterie on ne réveille plus le système
    nextStartDateValue = SecondsToDate(nextStartSecs + (3600 * 24 * 30))  # +30 jours
    getLogger().warning("No more battery: start in 30 days: %s", nextStartDateValue)

SetNextStartDate(nextStartDateValue)

StopTime = SecondsToDate(
    CurrentDateinS + (60 * 20)
)  # arret au bout de 20min par sécurité en cas d'erreur
setNextShutdownDate(StopTime)


# Etape 2 #############################################
# On lance le scan des images
# On execute le contenu du fichier ScanorhizeProcess.py
# On scanne les images et on les envoie à la plateforme Web
cmd = "python3 ScanorhizeProcess.py"
getLogger().warning(cmd)
try:
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=True
    )
except CalledProcessError as exc:
    getLogger().error(exc.stderr)

## On ne lance pas avec l'import, car s'il y a une erreur, le programme s'arrête
## import ScanorhizeProcess

# Etape 3 #############################################
# Peut-être à mettre dans un sous programme au cas où il y aurait des plantages
# On échange avec la plateforme Web pour envoyer les images et les paramètres

# On allume la clé 4G et on attend d'avoir le réseau


# Paramètres à envoyer au début du process
# A faire dans le serveur Flask pour initialiser les données
# getTokens()
Hub_ = HubData()
Hub_.ReadConfig()
volt, Hub_.batteryLevelPercent = ReadBatVoltCap()
Hub_.diskSpacePercent = USBSpace()[0]
Hub_.temperature = ReadTemp()
Hub_.WriteConfig()

getLogger().warning(
    "Bat: %s  USB: %s  Temp: %s",
    Hub_.batteryLevelPercent,
    Hub_.diskSpacePercent,
    Hub_.temperature,
)
SendParameters(Hub_)

# Ensuite on synchronise les images et les fichiers JSON
# A faire


# Etape 4 #############################################
# On éteint le Raspberry Pi et le WittyPi
if is_dev():
    getLogger().warning("Dev mode: on ne lance pas le shutdown et on n'ejecte pas la clé")
    sys.exit(0)

cmdeject = "sudo eject /dev/sda"
result = run(
    cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
)
getLogger().warning(cmdeject)

# On fixe l'heure d'arrêt, car des fois le Witty ne s'eteint pas sur le doShutdown()
# qui ne fait que le poweroff du Raspberry
date_now = GetCurrentDate()
secs_now = DateToSeconds(date_now)
date_new = SecondsToDate(secs_now + 30)
getLogger().warning("Next stop at: %s", date_new)
setNextShutdownDate(date_new)

# lance le poweroff du Raspberry et éteint le WittyPi
doShutdown()
