"""
Gestion des Scanners
"""

import os
import dataclasses
import json
from subprocess import run
from time import sleep

from Miscellaneous import InitGPIO, TurnPin_On, TurnPin_Off, WriteTimeLogfile
from DateUtils import SecondsToDate, DateToSeconds

X_MAX = 216
Y_MAX = 297

ConfigScannerPath = "ConfigFile/Scanner/"
ResolutionList = ["300", "600", "1200"]
ColorList = ["COLOR", "Gray", "Lineart"]


@dataclasses.dataclass
class ZoneRectangle:
    """
    Rectangle
    """

    l: int
    t: int
    x: int
    y: int

    def __init__(self, l, t, x, y):
        self.l = l
        self.t = t
        self.x = min(x, X_MAX)
        self.y = min(y, Y_MAX)


class ScannerData:
    """
    Définition des paramètres du scanner
    """

    # pylint: disable=too-many-instance-attributes
    ScannerName = ""
    mode = ColorList[0]
    resolution = ResolutionList[0]
    LastImgTime = ""
    LastImgFile = ""
    ZoneAcq = ZoneRectangle(0, 0, X_MAX, Y_MAX)
    quality = 5
    token = "token_bidon"
    UseServer = 0
    error = 0
    Campaign = "CampaignName"
    StartDate = "20241115T094500Z"  # next start if UseServer=1
    PeriodeS = "3600"  # next start if UseServer=0

    def printScanner(self):
        try:
            data = (
                self.ScannerName
                + " "
                + str(self.mode)
                + " "
                + str(self.resolution)
                + " "
                + str(self.LastImgTime)
                + " "
                + str(self.LastImgFile)
                + " "
                + str(self.ZoneAcq.l)
                + " "
                + str(self.ZoneAcq.t)
                + " "
                + str(self.ZoneAcq.x)
                + " "
                + str(self.ZoneAcq.y)
                + " "
                + str(self.quality)
                + " "
                + str(self.UseServer)
                + " "
                + str(self.Campaign)
                + " "
                + str(self.StartDate)
                + " "
                + str(self.PeriodeS)
            )
            print(data)
            # WriteLogFile(data)
        except ValueError:
            return 1
        return 0

    def ReadScannerConfig(self, file):
        fullpath = ConfigScannerPath + file
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)
        except ValueError:
            WriteTimeLogfile("No file: " + fullpath)
            WriteScannerConfig(self, file)
        else:
            # print(data)
            self.ScannerName = data["ScannerName"]
            self.mode = data["mode"]
            self.resolution = data["resolution"]
            self.LastImgTime = data["LastImgTime"]
            self.LastImgFile = data["LastImgFile"]
            self.ZoneAcq = ZoneRectangle(data["l"], data["t"], data["x"], data["y"])
            self.quality = data["quality"]
            self.token = data["token"]
            self.UseServer = data["UseServer"]
            self.Campaign = data["Campaign"]
            self.StartDate = data["StartDate"]
            self.PeriodeS = data["PeriodeS"]
        finally:
            self.printScanner()
        return self


# Initialisation de l'objet Scanner
Scanner = ScannerData()

def updateScanParameters(scanner: ScannerData):
    Scannerparam = {
        "scannerName": scanner.ScannerName,
        "mode": scanner.mode,
        "mode1": ColorList[0],
        "mode2": ColorList[1],
        "mode3": ColorList[2],
        "resolution": scanner.resolution,
        "resolution1": ResolutionList[0],
        "resolution2": ResolutionList[1],
        "resolution3": ResolutionList[2],
        "LastImgTime": scanner.LastImgTime,
        "LastImgFile": scanner.LastImgFile,
        "l": scanner.zoneAcq.l,
        "t": scanner.zoneAcq.t,
        "x": scanner.zoneAcq.x,
        "y": scanner.zoneAcq.y,
        "quality": scanner.quality,
        "token": scanner.token,
        "UseServer": scanner.UseServer,
        "Campaign": scanner.Campaign,
        "StartDate": scanner.StartDate,
        "PeriodeS": scanner.PeriodeS,
    }
    return Scannerparam


ScanNumber = 3
imagetiff = "imagescan.tiff"
imagepathtiff = "/home/pi/Scanorhize/static/" + imagetiff
imagepath = "/home/pi/Scanorhize/static/"
imagepathjp2000 = imagepath + "imagejp2000.jp2"


def scanSearch():
    # function to find scanner with sane
    res = 1
    i = 0
    while res != 0 and i < ScanNumber:
        cmd = "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage -L"
        print("i=", i)
        # print(cmd)
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=False
        )
        # print(result.returncode, result.stdout, result.stderr)
        res = result.returncode
        print(res, result.stdout)
        x = (result.stdout).split()
        # print(x)
        if x[0] == "No":
            res = 1
        i += 1
    if res == 0:
        x = (result.stdout).split("'")
        x = (result.stdout).split()
        ScannerName = x[1]
        ScannerName = ScannerName[1 : len(ScannerName) - 1]
    else:
        ScannerName = "NoScannerDetected"
        sleep(10)
    print("Scanner :", ScannerName)
    return ScannerName


def scanAcq(scanner: ScannerData, pin, date):
    error = TurnPin_On(pin, 40)
    if error != 0:
        scanner.error = 1
        return scanner
    Displayfile = "Log/Display.txt"
    command = (
        "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage --mode="
        + scanner.mode
        + " --resolution="
        + str(scanner.resolution)
        + " -l "
        + str(scanner.ZoneAcq.l)
        + " -t "
        + str(scanner.ZoneAcq.t)
        + " -x "
        + str(scanner.ZoneAcq.x)
        + " -y "
        + str(scanner.ZoneAcq.y)
        + " --format=tiff >"
        + imagepathtiff
        + " | tee -a "
        + Displayfile
    )
    print(command)
    res = 1
    i = 0
    while res != 0 and i < 2:
        # print("i=",i)
        WriteTimeLogfile("StartScan :" + str(i))
        result = run(
            command,
            capture_output=True,
            universal_newlines=True,
            shell=True,
            check=False,
        )
        WriteTimeLogfile(
            "code: "
            + str(result.returncode)
            + "stdout :"
            + str(result.stdout)
            + "stderr :"
            + str(result.stderr)
        )
        res = result.returncode
        if len(result.stderr) > 2:
            res = 12
        if (
            "no SANE" in result.stderr
            or "Error" in result.stderr
            or "failed" in result.stderr
        ):
            res = 12
        scanner.error = res
        i += 1
        if res != 0:
            TurnPin_Off(pin)
            TurnPin_On(pin, 40)

    TurnPin_Off(pin)
    if scanner.error > 0:
        WriteTimeLogfile("error acquisition: " + result.stdout + result.stderr)
        return scanner

    scanner.quality = min(scanner.quality, 90)

    commandconv = (
        'gdal_translate -of JP2OpenJPEG -co "QUALITY='
        + str(scanner.quality)
        + '" '
        + imagepathtiff
        + " "
        + imagepathjp2000
        + "| tee -a "
        + Displayfile
    )
    # print(commandconv)
    WriteTimeLogfile("Start conversion jp2")
    result = run(
        commandconv,
        capture_output=True,
        universal_newlines=True,
        shell=True,
        check=False,
    )
    print(result.returncode, result.stdout, result.stderr)
    scanner.error = result.returncode
    if scanner.error > 0:
        WriteTimeLogfile("Error conversion jp2")
        scanner.error = 20
        return scanner

    WriteTimeLogfile("EndConvTime")
    # Pour s'assurer que 2 images n'est pas le même temps et donc nom
    CurrentDateinS = DateToSeconds(date) + pin
    date = SecondsToDate(CurrentDateinS)
    scanner.LastImgTime = date
    # print("image time: ",scanner.LastImgTime)
    scanner.LastImgFile = imagepathjp2000
    # WriteTimeLogfile("EndscanAcqTime")
    return scanner


def ScannerPreview(pin):
    image = str(pin + 1) + ".jpg"
    error = TurnPin_On(pin, 40)
    if error != 0:
        Scanner.error = 1
        res = Scanner.error
        return image, res
    file = imagepath + image
    # On ne passe pas le device, car on n'allume qu'un port USB
    # donc scanimage va trouver le seul scanner sous tension !
    command = (
        "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage --mode="
        + Scanner.mode
        + " --resolution=75"
        + " --format=jpeg >"
        + file
    )
    # print(command)
    res = 1
    i = 0
    while res != 0 and i < 2:
        # print("i=",i)
        result = run(
            command,
            capture_output=True,
            universal_newlines=True,
            shell=True,
            check=False,
        )
        print(result.returncode, result.stdout, result.stderr)
        res = result.returncode
        if len(result.stderr) > 2:
            res = 12
        i += 1
    TurnPin_Off(pin)
    if res > 0:
        WriteTimeLogfile("error acquisition: " + result.stdout + result.stderr)
    else:
        WriteTimeLogfile("Preview OK")

    return image, res


def listConfigScanner():
    try:
        listfile = os.listdir(ConfigScannerPath)  # returns list
        # print(listfile)
        listfile.sort(reverse=False)
        WriteTimeLogfile(listfile)
    except OSError:
        listfile = ["1-Scanner.json", "2-Scanner.json", "3-Scanner.json"]
    return listfile


def WriteScannerConfig(scanner, file):
    # printScanner(scanner)
    data = {
        "ScannerName": scanner.ScannerName,
        "mode": scanner.mode,
        "resolution": scanner.resolution,
        "LastImgTime": scanner.LastImgTime,
        "LastImgFile": scanner.LastImgFile,
        "l": scanner.ZoneAcq.l,
        "t": scanner.ZoneAcq.t,
        "x": scanner.ZoneAcq.x,
        "y": scanner.ZoneAcq.y,
        "quality": scanner.quality,
        "token": scanner.token,
        "UseServer": scanner.UseServer,
        "Campaign": scanner.Campaign,
        "StartDate": scanner.StartDate,
        "PeriodeS": scanner.PeriodeS,
    }
    try:
        # printScanner(scanner)
        json_object = json.dumps(data, indent=len(data))
        fullpath = ConfigScannerPath + file
        # print(fullpath)
        with open(fullpath, "w", encoding="utf-8") as outfile:
            outfile.write(json_object)
    except ValueError:
        return 1
    return 0


if __name__ == "__main__":

    InitGPIO()
    result_ = ScannerPreview(0)
    Scanner.LastImgFile = result_[0]
    Scanner.error = result_[1]
    # WriteScannerConfig(Scanner, "1-Scanner.json")
