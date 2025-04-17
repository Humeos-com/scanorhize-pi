"""
Fait l'acquisition des images selon les paramètres des scanners
Les images sont stockées sur le disque USB
Les images seront envoyées par le processus ScanorhizeStart.py
"""

from time import sleep
from os import path

from ConfigApp import getLogger
from Scanner import listConfigScanner, scanAcq, ScannerData

from Miscellaneous import (
    InitGPIO,
    WriteStartDateConfig,
    ReadStartDateConfig,
    initDisplayFile,
)
from Campaign import CopyImageToUSB, CreateFolderOnUSB
from DateUtils import CalculNextStartDate, DateToSeconds, GetCurrentDate

DateStart = GetCurrentDate()
initDisplayFile()
getLogger().warning("StartProcess")
res = InitGPIO()
if res != 0:
    getLogger().error("InitGPIOError")

# init
Scanner = ScannerData()
NextStartseconds = [0, 0, 0]
NextStartDates = [" ", " ", " "]

listScannerconfigs = listConfigScanner()
scanning = 0
internet = 1
NextStartDates = ReadStartDateConfig()
i_scan = 0
for dates in NextStartDates:
    NextStartseconds[i_scan] = DateToSeconds(dates)
    i_scan = i_scan + 1


i_scan = 0
for CurrentScanner in listScannerconfigs:
    Scanner.ReadScannerConfig(CurrentScanner)
    if not Scanner.enable:
        getLogger().warning("Scanner %s is disabled", str(i_scan + 1))
        continue

    data = "scanner file: " + CurrentScanner
    getLogger().warning(data)

    DateOriginS = DateToSeconds(Scanner.StartDate)
    CurrentDateinS = DateToSeconds(DateStart)
    data = (
        "Scanner : "
        + Scanner.StartDate
        + " "
        + str(DateOriginS)
        + " Current : "
        + DateStart
        + " "
        + str(CurrentDateinS)
        + " NextStart : "
        + str(NextStartDates[i_scan])
    )
    getLogger().warning(data)

    if CurrentDateinS > DateOriginS and CurrentDateinS >= NextStartseconds[i_scan]:

        # get image from scanner
        getLogger().warning("Scanner %s: start image acquisition", str(i_scan + 1))
        Scanner = scanAcq(Scanner, i_scan, DateStart)
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
    # Prepare next StartDate for Scanner
    nextDate, nextDateS = CalculNextStartDate(
        Scanner.StartDate, Scanner.PeriodeS, DateStart
    )
    NextStartDates[i_scan] = nextDate
    getLogger().warning("Next start date: %s", nextDate)
    i_scan = i_scan + 1
# fin for

WriteStartDateConfig(NextStartDates)
