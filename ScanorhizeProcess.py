"""
Main process for Scanorhize: fait l'acquisition, envoie les images à la plateforme Web et éteint le système.
"""

import sys
from time import sleep
from subprocess import run
import numpy as np

from Scanner import listConfigScanner, WriteScannerConfig, scanAcq, ScannerData

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
from I2C import ReadBatVoltCap
from WittyPy import SetNextStartDate, ReadTemp
from DateUtils import CalculNextStartDate, DateToSeconds, GetCurrentDate

DateStart = GetCurrentDate()
initDisplayFile()
WriteTimeLogfile("StartProcess")
res = InitGPIO()
if res != 0:
    WriteTimeLogfile("InitGPIOError")
Bat = ReadBatVoltCap()
Temperature = ReadTemp()

# init
Scanner = ScannerData()
NextStartseconds = [0, 0, 0]
NextStartDate = [" ", " ", " "]

listScannerconfigs = listConfigScanner()
i_scan = 0
scanning = 0
internet = 1
DatesSaved = ReadStartDateConfig()
NextStartDate = DatesSaved[0]
NextStartseconds = DatesSaved[1]

for CurrentScanner in listScannerconfigs:
    Scanner.ReadScannerConfig(CurrentScanner)
    data = "scanner file: " + CurrentScanner
    WriteTimeLogfile(data)

    ScannerStartinS = DateToSeconds(Scanner.StartDate)
    CurrentDateinS = DateToSeconds(DateStart)
    data = (
        "Scanner : "
        + Scanner.StartDate
        + " "
        + str(ScannerStartinS)
        + " Current : "
        + DateStart
        + " "
        + str(CurrentDateinS)
        + " NextStart : "
        + str(NextStartseconds[i_scan])
    )
    WriteTimeLogfile(data)

    if CurrentDateinS > ScannerStartinS and CurrentDateinS >= NextStartseconds[i_scan]:
        WriteTimeLogfile("Turn scanner" + str(i_scan + 1) + " On")

        # get image and post image
        WriteTimeLogfile("Start image acquisition")
        Scanner = scanAcq(Scanner, i_scan, DateStart)
        WriteScannerConfig(Scanner, CurrentScanner)
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

            USB = USBSpace()
            WriteTimeLogfile(
                "Bat :"
                + str(Bat[1])
                + "USB :"
                + str(USB[0])
                + "Temp :"
                + str(Temperature)
            )
            SendParameters(Scanner, Bat[1], USB[0], Temperature)
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
        WriteScannerConfig(Scanner, listScannerconfigs[i_scan])

    nextDate = CalculNextStartDate(Scanner.StartDate, Scanner.PeriodeS, DateStart)
    nextTime = DateToSeconds(nextDate)
    NextStartseconds[i_scan] = nextTime
    NextStartDate[i_scan] = nextDate
    WriteTimeLogfile("Next start date: " + nextDate)
    i_scan = i_scan + 1

WriteStartDateConfig(NextStartDate, NextStartseconds)
nextStartSecs = min(NextStartseconds)
index_min = np.argmin(NextStartseconds)
nextStartDateValue = NextStartDate[index_min]
WriteTimeLogfile("Next start at: " + nextStartDateValue)

if Bat[1] < 0:  # si plus de batterie on ne réveille plus le système
    nextStartDateValue = CalculNextStartDate(
        Scanner.StartDate, (3600 * 24 * 30), DateStart
    )
    WriteTimeLogfile("No more battery")
# fin for

SetNextStartDate(nextStartDateValue)

if is_dev():
    print("Dev mode: on ne lance pas le shutdown et on n'ejecte pas la clé")
    sys.exit(0)

# CopyLog()
cmdeject = "sudo eject /dev/sda"
result = run(
    cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
)
WriteTimeLogfile(cmdeject)
cmd = "sudo shutdown -P now"
result = run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
