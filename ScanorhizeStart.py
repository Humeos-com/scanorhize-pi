"""Lance le scanner et programme le prochain réveil"
On gère les GPIO pour la carte 4G depuis ce programme
"""

import sys
from subprocess import run, CalledProcessError

from WittyPy import SetNextStartDate, doShutdown, setNextShutdownDate
from WittyPython import ReadTemp
from Miscellaneous import (
    EndGPIO,
    enable4G,
    disable4G,
    check_connectivity,
    ReadGPIOConfig,
    ReadBatVoltCap,
)
from DateUtils import GetCurrentDate, SecondsToDate, DateToSeconds, CalculNextStartDate
from ConfigApp import is_dev, getLogger
from Scanner import listConfigScanner, ScannerData
from Hub import HubData, SendParameters, syncImageFiles, ReadScannerConfigFromServer
from Campaign import USBSpace

getLogger().warning("ScanorhizeStart.py")

# On regarde si on est en mode configuration
config = ReadGPIOConfig()
EndGPIO()

if config == 0:
    # En mode config
    if enable4G():
        getLogger().warning("4G enabled")

    cmd = "nohup python3 Scanorhize.py > /dev/null 2>&1 &"
    getLogger().warning(cmd)
    result = run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
    if result.returncode == 0:
        getLogger().warning("Scanorhize.py started successfully")
        sys.exit(0)
    else:
        getLogger().error("Failed to start Scanorhize.py: %s", result.stderr)
        sys.exit(1)

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
    getLogger().warning("Scanner-%s: Next start date: %s", i_scan + 1, nextDate)
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
# Transfert des données

try:
    # On allume la clé 4G et on attend d'avoir le réseau
    enable4G()
    # Teste la connectivité
    check_connectivity()

    # On synchronise l'horloge de la carte WittyPi avec le serveur
    try:
        cmd = "sudo ./TimeSynchronisation.sh"
        getLogger().warning(cmd)
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=False
        )
    except CalledProcessError as exc:
        getLogger().error(exc.stderr)

    #
    # Etape 4 #############################################
    # On lance un sous programme qui met à jour toutes les données sur la plateforme
    # On échange avec la plateforme Web pour envoyer les images et les paramètres

    # On récupère les configs des scanners depuis la plateforme / le S3 ??
    # avec la TODO liste
    # selon le flag Scanner.UseServer

    # Paramètres
    Hub_ = HubData()
    Hub_.ReadConfig()
    volt, Hub_.batteryLevelPercent = ReadBatVoltCap()
    Hub_.diskSpacePercent = USBSpace()[0] / 1000
    Hub_.temperature = ReadTemp()
    Hub_.WriteConfig()

    getLogger().warning(
        "Bat: %s  USB: %s  Temp: %s",
        Hub_.batteryLevelPercent,
        Hub_.diskSpacePercent,
        Hub_.temperature,
    )
    SendParameters(Hub_)  ## Plutôt envoie les paramètres au S3 ??
    syncImageFiles(Hub_)

    # On recupère les configuration des Scanners en fonction de use_server
    i_scan = 0
    for CurrentScanner in listScannerconfigs:
        Scanner.ReadScannerConfig(CurrentScanner)
        if Scanner.UseServer:
            ReadScannerConfigFromServer(Scanner)

except RuntimeError as exc:
    getLogger().error(exc)

finally:
    # On éteint la clé 4G
    disable4G()


# Etape 4 #############################################
# On éteint le Raspberry Pi et le WittyPi
if is_dev():
    getLogger().warning(
        "Dev mode: on ne lance pas le shutdown et on n'ejecte pas la clé"
    )
    sys.exit(0)

cmdeject = "sudo eject /dev/sda"
result = run(
    cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
)
getLogger().warning(cmdeject)

# On fixe l'heure d'arrêt dans 30 secondes,
# car des fois le Witty ne s'eteint pas sur le doShutdown()
date_now = GetCurrentDate()
secs_now = DateToSeconds(date_now)
date_new = SecondsToDate(secs_now + 30)
getLogger().warning("Next stop at: %s", date_new)
setNextShutdownDate(date_new)

# lance le poweroff du Raspberry et éteint le WittyPi
# en principe le doShutdown() lance le shutdown -h now,
# sauf s'il y a un fichier /boot/wittypi.lock
# Donc on ajoute un poweroff en plus...
getLogger().warning("doShutdown until: %s", nextStartDateValue)
doShutdown()
cmd = "sudo poweroff"
getLogger().warning(cmd)
result = run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
sys.exit(0)
