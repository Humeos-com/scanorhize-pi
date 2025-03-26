"""
Main process for Scanorhize: fait l'acquisition,
 envoie les images à la plateforme Web et éteint le système.
"""

from time import sleep

from Scanner import listConfigScanner, scanAcq, ScannerData

from Server import HubData, getTokens, SendParameters, PostImageToServer, ReadConfigFromServer
from Miscellaneous import (
    WriteTimeLogfile,
    InitGPIO,
    WriteStartDateConfig,
    ReadStartDateConfig,
    initDisplayFile,
)
from Campaign import CreateFolderImage, CopyImageToUSB, USBSpace
from WittyPython import ReadBatVoltCap, ReadTemp
from DateUtils import CalculNextStartDate, DateToSeconds, GetCurrentDate

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
# A faire dans le serveur Flask pour initialiser les données
# getTokens()
Hub_ = HubData()
Hub_.ReadConfig()
volt, Hub_.batteryLevelPercent = ReadBatVoltCap()
Hub_.diskSpacePercent = USBSpace()[0]
Hub_.temperature = ReadTemp()
Hub_.WriteConfig()

WriteTimeLogfile(f"Bat: {Hub_.batteryLevelPercent}  " f"USB: {Hub_.diskSpacePercent}  " f"Temp: {Hub_.temperature}")
SendParameters(Hub_)

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
