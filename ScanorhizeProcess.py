"""
Main process for Scanorhize: fait l'acquisition,
 envoie les images à la plateforme Web et éteint le système.
"""

from time import sleep
from os import path

from ConfigApp import getLogger
from Scanner import listConfigScanner, scanAcq, ScannerData

from Server import (
    ReadConfigFromServer,
)
from Miscellaneous import (
    InitGPIO,
    WriteStartDateConfig,
    ReadStartDateConfig,
    initDisplayFile,
)
from Campaign import CopyImageToUSB,CreateFolderOnUSB
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
        getLogger().warning("Turn scanner %s On", str(i_scan + 1))

        # get image and post image
        getLogger().warning("Start image acquisition")
        Scanner = scanAcq(Scanner, i_scan, DateStart)
        Scanner.WriteScannerConfig(CurrentScanner)
        scanning = 1
        if Scanner.error == 0:
            getLogger().warning("Image acquisition Ok")
            sleep(5) # Voir si on peut réduire ce timer
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
    if Scanner.UseServer == 1:
        getLogger().warning("Get Scanner config from server")
        Scanner = ReadConfigFromServer(Scanner)
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])

    nextDate, nextDateS = CalculNextStartDate(
        Scanner.StartDate, Scanner.PeriodeS, DateStart
    )
    NextStartDates[i_scan] = nextDate
    getLogger().warning("Next start date: %s", nextDate)
    i_scan = i_scan + 1
# fin for

WriteStartDateConfig(NextStartDates)
