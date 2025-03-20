"""
Main process for Scanorhize: fait l'acquisition,
 envoie les images à la plateforme Web et éteint le système.
"""

import sys
from time import sleep
from subprocess import run
import numpy as np

from Scanner import listConfigScanner, scanAcq, ScannerData

from Server import SendParameters, PostImageToServer, ReadConfigFromServer
from Miscellaneous import (
    WriteTimeLogfile,
    InitGPIO,
    WriteStartDateConfig,
    ReadStartDateConfig,
    initDisplayFile,
)
from OSUtils import is_dev
from Campaign import CreateFolderImage, CopyImageToUSB, USBSpace
from WittyPython import ReadBatVoltCap, ReadTemp
from WittyPy import SetNextStartDate, doShutdown, setNextShutdownDate
from DateUtils import CalculNextStartDate, DateToSeconds, SecondsToDate, GetCurrentDate

DateStart = GetCurrentDate()
initDisplayFile()
WriteTimeLogfile("StartProcess")
res = InitGPIO()
if res != 0:
    WriteTimeLogfile("InitGPIOError")

# init
Scanner = ScannerData()
NextStartseconds = [0, 0, 0]
NextStartDate = [" ", " ", " "]

listScannerconfigs = listConfigScanner()
scanning = 0
internet = 1
NextStartDate = ReadStartDateConfig()
i_scan = 0
for dates in NextStartDate:
    NextStartseconds[i_scan] = DateToSeconds(dates)
    i_scan = i_scan + 1

# Paramètres à envoyer au début du process
Bat = ReadBatVoltCap()
Temperature = ReadTemp()
USB = USBSpace()
WriteTimeLogfile(f"Bat: {Bat[1]}  " f"USB: {USB[0]}  " f"Temp: {Temperature}")
SendParameters(Scanner, Bat[1], USB[0], Temperature)

i_scan = 0
for CurrentScanner in listScannerconfigs:
    Scanner.ReadScannerConfig(CurrentScanner)
    data = "scanner file: " + CurrentScanner
    WriteTimeLogfile(data)

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
        + str(NextStartDate[i_scan])
    )
    WriteTimeLogfile(data)

    if CurrentDateinS > DateOriginS and CurrentDateinS >= NextStartseconds[i_scan]:
        WriteTimeLogfile("Turn scanner" + str(i_scan + 1) + " On")

        # get image and post image
        WriteTimeLogfile("Start image acquisition")
        Scanner = scanAcq(Scanner, i_scan, DateStart)
        Scanner.WriteScannerConfig(CurrentScanner)
        scanning = 1
        if Scanner.error == 0:
            WriteTimeLogfile("Image acquisition Ok")
            sleep(5)
            FolderImage = CreateFolderImage(Scanner.Campaign, i_scan)
            copyerror = CopyImageToUSB(Scanner, FolderImage)
            if copyerror == 0:
                WriteTimeLogfile("Image copied to USB")
            else:
                WriteTimeLogfile("Error in copy to USB")

            WriteTimeLogfile("StartPostImage")
            PostError = PostImageToServer(Scanner)
            if PostError != 0:
                WriteTimeLogfile("Post error")
            else:
                WriteTimeLogfile("EndPost OK")
        else:
            WriteTimeLogfile("Image acquisition Error")
    # Prepare next StartDate for Scanner
    if Scanner.UseServer == 1:
        data = "Scanner config from server"
        WriteTimeLogfile(str(data))
        Scanner = ReadConfigFromServer(Scanner)
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])

    nextDate, nextDateS = CalculNextStartDate(
        Scanner.StartDate, Scanner.PeriodeS, DateStart
    )
    NextStartDate[i_scan] = nextDate
    WriteTimeLogfile("Next start date: " + nextDate)
    i_scan = i_scan + 1
# fin for

WriteStartDateConfig(NextStartDate)
nextStartSecs = min(NextStartseconds)
index_min = np.argmin(NextStartseconds)
nextStartDateValue = NextStartDate[index_min]
WriteTimeLogfile("Next start at: " + nextStartDateValue)

if Bat[1] < 0:  # si plus de batterie on ne réveille plus le système
    nextStartDateValue = CalculNextStartDate(
        Scanner.StartDate, (3600 * 24 * 30), DateStart
    )
    WriteTimeLogfile("No more battery")

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
date_new = GetCurrentDate()
secs = DateToSeconds(date_new)
date_new = SecondsToDate(secs + 30)
WriteTimeLogfile("Next stop at: " + date_new)
setNextShutdownDate(date_new)

# lance le poweroff du Raspberry et éteint le WittyPi
doShutdown()
# cmd = "sudo shutdown -P now"
# result = run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
