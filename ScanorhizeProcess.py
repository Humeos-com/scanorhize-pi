"""
Fait l'acquisition des images selon les paramètres des scanners
Si cette tâche est lancée, c'est suite à un réveil du WittyPi.
C'est qu'il y a probablement des acquisitions à faire.
Donc chaque scanner va regarder si sa date de déclenchement se trouve dans les 10 minutes avant
la date courante.
En effet, on démarre le WittyPi à la date théorique d'acquisition.
Mais, quand on est dans ce processus, la date est donc passée (temps du boot, etc...) mais de quelques minutes.
On se laisse une marge de 10 minutes pour considérer qu'il faut lancer l'acquisition.
Si on est au delà des 10 minutes, on ne fait rien, c'est qu'on a allumé le WittyPi à la main.

Les images sont stockées sur le disque USB
Les images seront envoyées par le processus ScanorhizeStart.py
"""

from time import sleep
from os import path

from ConfigApp import getLogger, getDeltaTime
from Scanner import listConfigScanner, scanAcq, ScannerData

from Miscellaneous import (
    InitGPIO,
    initDisplayFile,
)
from Campaign import CopyImageToUSB, CreateFolderOnUSB
from DateUtils import CalculNextStartDate, DateToSeconds, GetCurrentDate

CurrentDate = GetCurrentDate()
CurrentDateinS = DateToSeconds(CurrentDate)
initDisplayFile()
getLogger().warning("StartProcess")
res = InitGPIO()
if res != 0:
    getLogger().error("InitGPIOError")

# init
Scanner = ScannerData()
listScannerconfigs = listConfigScanner()
scanning = 0

i_scan = 0
for CurrentScanner in listScannerconfigs:
    Scanner.ReadScannerConfig(CurrentScanner)
    if not Scanner.enable:
        getLogger().warning("Scanner %s is disabled", str(i_scan + 1))
        i_scan = i_scan + 1
        continue

    data = "Scanner file: " + CurrentScanner
    getLogger().warning(data)

    DateOriginS = DateToSeconds(Scanner.StartDate)
    NextStartDate, NextStartseconds = CalculNextStartDate(
        Scanner.StartDate, Scanner.PeriodeS, CurrentDate
    )
    NextStartseconds = NextStartseconds - Scanner.PeriodeS
    # On déclenche l'acquisition si la date courante voisine à DeltaTime près de la date de déclenchement
    if (
        CurrentDateinS > DateOriginS
        and NextStartseconds <= CurrentDateinS <= NextStartseconds + getDeltaTime()
    ):
        # get image from scanner
        getLogger().warning("Scanner %s: start image acquisition", str(i_scan + 1))
        Scanner = scanAcq(Scanner, i_scan, CurrentDate)
        Scanner.WriteScannerConfig(CurrentScanner)
        scanning = 1
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
        else:
            getLogger().error("Image acquisition Error")
    else:
        getLogger().warning(
            "Scanner %s: no acquisition. DateStart %s too far from NextStartDate %s",
            str(i_scan + 1),
            CurrentDateinS,
            NextStartseconds,
        )
    i_scan = i_scan + 1
# fin for
