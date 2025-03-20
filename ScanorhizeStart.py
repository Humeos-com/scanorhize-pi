"""Lance le scanner et programme le prochain réveil"""

import sys
from subprocess import call, run

from WittyPy import SetNextStartDate, doShutdown, setNextShutdownDate
from WittyPython import ReadBatVoltCap
from Miscellaneous import (
    InitGPIO,
    TurnUsbOn,
    ReadGPIOConfig,
    WriteTimeLogfile,
    ReadStartDateConfig,
)
from DateUtils import GetCurrentDate, SecondsToDate, DateToSeconds
from OSUtils import is_dev

WriteTimeLogfile("ScanorhizeStart.py")

res = InitGPIO()
if res != 0:
    WriteTimeLogfile("InitGPIOError")
# On allume la clé 4G
res = TurnUsbOn(3, 0)
if res != 0:
    WriteTimeLogfile("TurnUsbOnError")

config = ReadGPIOConfig()
config = 1

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
    WriteTimeLogfile(cmd)
    call(cmd, shell=True)
    sys.exit(1)


DateStart = GetCurrentDate()
CurrentDateinS = DateToSeconds(DateStart)
NextDate = SecondsToDate(CurrentDateinS + (3600 * 1))  # demarrage toutes les 1h
StopTime = SecondsToDate(
    CurrentDateinS + (60 * 20)
)  # arret au bout de 20min par sécurité en cas d'erreur
WriteTimeLogfile("Set NextDate: " + NextDate)
SetNextStartDate(NextDate)

# pylint: disable=wrong-import-position, disable=unused-import
# On execute le contenu du fichier ScanorhizeProcess.py
# On scanne les images et on les envoie à la plateforme Web
cmd = "python3 ScanorhizeProcess.py"
WriteTimeLogfile(cmd)
call(cmd, shell=True)
result = run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)

## On ne lance pas par l'import, car s'il y a une erreur, le programme s'arrête
## import ScanorhizeProcess

# On détermine la prochaine date de réveil
NextStartseconds = [0, 0, 0]
NextStartDate = [" ", " ", " "]

NextStartDate = ReadStartDateConfig()
date_now = GetCurrentDate()
secs_now = DateToSeconds(date_now)
i_scan = 0
for dates in NextStartDate:
    NextStartseconds[i_scan] = DateToSeconds(dates)
    i_scan = i_scan + 1

# Quand la carte WittyPi n'a plus de batterie, son heure interne est aléatoire.
# Lorsque les acquisitions ne fonctionne pas, la nextStartDate ne bouge pas.
# Donc elle se retrouve dans le passé. Avec un minimum de secs_now + 600, on
# espère que la carte WittyPi se réveillera.
nextStartSecs = max(int(min(NextStartseconds)), (secs_now + 600))
nextStartDateValue = SecondsToDate(nextStartSecs)
WriteTimeLogfile("Next start at: " + nextStartDateValue)

Bat = ReadBatVoltCap()
if Bat[1] < 0:  # si plus de batterie on ne réveille plus le système
    nextStartDateValue = SecondsToDate(nextStartSecs + (3600 * 24 * 30))  # +30 jours
    WriteTimeLogfile("No more battery: start in 30 days")

SetNextStartDate(nextStartDateValue)

if is_dev():
    WriteTimeLogfile("Dev mode: on ne lance pas le shutdown et on n'ejecte pas la clé")
    sys.exit(0)

# CopyLog()
cmdeject = "sudo eject /dev/sda"
result = run(
    cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
)
WriteTimeLogfile(cmdeject)

# On fixe l'heure d'arrêt, car des fois le Witty ne s'eteint pas sur le doShutdown()
# qui ne fait que le poweroff du Raspberry
date_new = SecondsToDate(secs_now + 30)
WriteTimeLogfile("Next stop at: " + date_new)
setNextShutdownDate(date_new)

# lance le poweroff du Raspberry et éteint le WittyPi
doShutdown()
