#!/usr/bin/env python3
"""
Fait l'acquisition des images selon les paramètres des scanners
Si cette tâche est lancée, c'est suite à un réveil du WittyPi.
C'est qu'il y a probablement des acquisitions à faire.
Chaque scanner va regarder si sa date de déclenchement se trouve dans les 10 minutes (delta_time) avant
la date courante.
En effet, on démarre le WittyPi à la date théorique d'acquisition.
Mais, quand on est dans ce processus, la date est donc passée (temps du boot, etc...) mais de quelques minutes.
On se laisse une marge de delta_time pour considérer qu'il faut lancer l'acquisition.
Si on est au delà de delta_time, on ne fait rien, c'est qu'on a allumé le WittyPi à la main.

Les images sont stockées sur le disque USB
Les images seront envoyées par le processus ScanorhizeStart.py
"""

from time import sleep
import sys
from os import path
import argparse
from version import __version__

from ConfigApp import getLogger
from Hub import (
    getSyncImages,
    syncImageFiles,
    HubData,
    calculate_next_wakeup_from_crontab,
)
from Scanner import listConfigScanner, scanAcq, ScannerData

from Miscellaneous import (
    InitGPIO,
    initDisplayFile,
)
from Campaign import CopyImageToUSB, CreateFolderOnUSB
from DateUtils import GetCurrentDate

parser = argparse.ArgumentParser(
    prog="ScanorhizeProcess.py",
    usage="%(prog)s [--force] [--version]",
    epilog="""Lance l'aquisition des images. --force force l'acquisition même si la date de déclenchement n'est pas atteinte""",
)
parser.add_argument(
    "-f",
    "--force",
    action="store_true",
    help="Force l'acquisition même si la date de déclenchement n'est pas atteinte",
)
# pylint: disable=duplicate-code
parser.add_argument(
    "-v",
    "--version",
    action="store_true",
    help="Affiche la version du programme",
)

args = parser.parse_args()
if args.version:
    print(f"ScanorhizeProcess.py version: {__version__}")
    sys.exit(0)

force = bool(args.force)

CurrentDate = GetCurrentDate()
initDisplayFile()
getLogger().warning("StartProcess")
res = InitGPIO()
if res != 0:
    getLogger().error("InitGPIOError")

# init
Scanner = ScannerData()
listScannerconfigs = listConfigScanner()
scanning_error = 0

i_scan = 0
for CurrentScanner in listScannerconfigs:
    Scanner.ReadScannerConfig(CurrentScanner)
    if not Scanner.enable:
        getLogger().warning("Scanner %s is disabled", str(i_scan + 1))
        i_scan = i_scan + 1
        continue

    data = "Scanner file: " + CurrentScanner
    getLogger().warning(data)

    # Plus besoin de vérifier NextStartDate pour chaque scanner
    # Si on est réveillé, c'est qu'il faut acquérir (selon crontab Hub)
    if force or True:  # Tous les scanners actifs acquièrent
        if force:
            getLogger().warning("Force acquisition")
        # get image from scanner
        getLogger().warning("Scanner %s: start image acquisition", str(i_scan + 1))
        Scanner = scanAcq(Scanner, i_scan, CurrentDate)
        Scanner.WriteScannerConfig(CurrentScanner)
        if Scanner.error == 0:
            getLogger().warning("Image acquisition Ok")
            sleep(5)  # Voir si on peut réduire ce timer
            FolderImage = CreateFolderOnUSB(Scanner.projectId)
            FolderImage = CreateFolderOnUSB(path.join(FolderImage, Scanner.sampleId))
            copyerror = CopyImageToUSB(Scanner, FolderImage)
            if copyerror == 0:
                getLogger().warning("Image copied to USB")
            else:
                getLogger().error("Error in copy to USB")
                scanning_error = 1

        else:
            getLogger().error("Image acquisition Error")
            scanning_error = 1
    i_scan = i_scan + 1
# fin for

if force:
    # On peut travailler sans synchroniser les images si le réseau est mauvais
    # ou si les images sont trop grosses pour le réseau
    Hub = HubData()
    Hub.read_config()
    if getSyncImages():
        syncImageFiles(Hub)

# Calculer et configurer le prochain réveil
next_wakeup = calculate_next_wakeup_from_crontab()
getLogger().warning("Next scheduled wakeup: %s", next_wakeup)

sys.exit(scanning_error)
