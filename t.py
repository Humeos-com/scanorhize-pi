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


SetNextStartDate(nextStartDateValue)

