"""
Gestion des Scanners
"""

import os
import sys
import re
import dataclasses
import json
from subprocess import run

from Miscellaneous import InitGPIO, TurnUsbOn, TurnUsbOff, WriteTimeLogfile
from DateUtils import SecondsToDate, DateToSeconds
from OSUtils import is_raspberry_pi
from ConfigApp import is_dev

X_MAX = 216
Y_MAX = 297
TIME_USB_READY = 40
TIME_AFTER_SCAN = 10
if is_dev():
    TIME_USB_READY = 10
    TIME_AFTER_SCAN = 10
if not is_raspberry_pi():
    TIME_USB_READY = 0
    TIME_AFTER_SCAN = 0


CONFIG_PATH = "ConfigFile/Scanner/"
DISPLAY_FILE = "Log/Display.txt"
ResolutionList = ["300", "600", "1200"]
ColorList = ["Color", "Gray", "Lineart"]


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
    device = "NoScannerDetected"  # le device au sens SANE usb+fabricant+#série
    token = "token_bidon"
    projectId = ""
    sampleId = ""
    UseServer = 0
    error = 0
    Campaign = "CampaignName"
    StartDate = "2024-11-15T09:45:00Z"  # next start if UseServer=1
    PeriodeS = 3600  # next start if UseServer=0

    def printScanner(self):
        for name, value in self.__dict__.items():
            print(f"{name}: {value}")

    def ReadScannerConfig(self, file=""):
        fullpath = os.path.join(CONFIG_PATH, file)
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)  # Load JSON into a dictionary
            # Convert ZoneAcq dict back to ZoneRectangle object
            if "ZoneAcq" in data:
                zone_data = data["ZoneAcq"]
                data["ZoneAcq"] = ZoneRectangle(
                    zone_data["l"], zone_data["t"], zone_data["x"], zone_data["y"]
                )
        except (FileNotFoundError, ValueError):
            WriteTimeLogfile(f"No file: {fullpath}")
            ## self.WriteScannerConfig(file)
        else:
            self.__dict__.update(data)
        finally:
            self.printScanner()
        return self

    def WriteScannerConfig(self, file):
        fullpath = os.path.join(CONFIG_PATH, file)
        json_data = self.json()
        try:
            with open(fullpath, "w", encoding="utf-8") as outfile:
                outfile.write(json_data)
        except OSError as e:
            WriteTimeLogfile(f"WriteScannerConfig Error: {e}")
            return 1
        return 0

    def json(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__,
            sort_keys=True,
            ensure_ascii=False,
            indent=4,
        )

    def scanSearch(self, i_scan: int):
        # function to find scanner with sane
        # on cherche le scanners pour enregistrer le nom du device
        error = TurnUsbOn(i_scan, TIME_USB_READY)
        if error != 0:
            self.error = 1
            return self

        res = 1
        i = 0
        scanimage_message = "No scanners were identified"
        if is_raspberry_pi():
            cmd = (
                "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage -L | tee -a "
                + DISPLAY_FILE
            )
            print("i=", i)
            # print(cmd)
            result = run(
                cmd,
                capture_output=True,
                universal_newlines=True,
                shell=True,
                check=False,
            )
            # print(result.returncode, result.stdout, result.stderr)
            res = result.returncode
            scanimage_message = result.stdout
            print(res, scanimage_message)
            x = (scanimage_message).split()
            # print(x)
            if x[0] == "No":
                res = 1
        else:
            # fake scanimage message
            res = 0
            scanimage_message = """device `pixma:00000_ABABAB' \
 is a CANON CanoScan LiDE 400 multi-function peripheral"""

        self.device = "NoScannerDetected"
        if res == 0:
            for line in scanimage_message.splitlines():
                x = (line).split("'")
                x = (line).split()
                device = x[1]
                self.device = device[1 : len(device) - 1]
        else:
            self.device = "NoScannerDetected"
        print("Scanner :", self.device)
        TurnUsbOff(i_scan)
        if self.error > 0:
            WriteTimeLogfile("error acquisition: " + result.stdout + result.stderr)

        return self


# Initialisation de l'objet Scanner
Scanner = ScannerData()


def extract_serial(device_string: str) -> str:
    """Extract serial number from device string

    Args:
        device_string (str): Device string in format 'pixma:SERIAL'

    Returns:
        str: Serial number part after the colon, or empty string if invalid format
    """
    try:
        parts = device_string.split(":")
        return parts[1] if len(parts) > 1 else ""
    except (IndexError, AttributeError):
        return ""


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
        "l": scanner.ZoneAcq.l,
        "t": scanner.ZoneAcq.t,
        "x": scanner.ZoneAcq.x,
        "y": scanner.ZoneAcq.y,
        "quality": scanner.quality,
        "device": scanner.device,
        "token": scanner.token,
        "UseServer": scanner.UseServer,
        "Campaign": scanner.Campaign,
        "StartDate": scanner.StartDate,
        "PeriodeS": scanner.PeriodeS,
    }
    return Scannerparam


ScanNumber = 3
imagetiff = "imagescan.tiff"
# imagepathtiff = "/home/pi/Scanorhize/static/" + imagetiff
# imagepath = "/home/pi/Scanorhize/static/"
imagepathtiff = "static/" + imagetiff
imagepath = "static/"
imagepathjp2000 = imagepath + "imagejp2000.jp2"


def scanAcq(scanner: ScannerData, i_scan: int, date):
    """Lance le scanimage et convertit l'image en jp2000

    Args:
        scanner (ScannerData): l'objet Scanner en cours
        i_scan (int): de 0 à 2 pour les 3 scanners
        date (_type_):

    Returns:
        _type_: _description_
    """

    WriteTimeLogfile(f"scanAcq: on allume le port USB: {i_scan + 1}")
    error = TurnUsbOn(i_scan, TIME_USB_READY)
    if error != 0:
        scanner.error = 1
        return scanner

    if scanner.device == "NoScannerDetected":
        option_device = ""
    else:
        option_device = ' --device="' + scanner.device + '"'
    # On n'utilise pas le device pour l'instant, car sinon, il faut respecter le cablage...
    option_device = ""
    command = (
        "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage"
        + option_device
        + " --mode="
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
        + DISPLAY_FILE
    )
    WriteTimeLogfile("scanAcq: " + command)
    res = 1
    i = 0
    while res != 0 and i < 2:
        # print("i=",i)
        WriteTimeLogfile("StartScan :" + str(i))
        if is_raspberry_pi():
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
        # if res != 0:
        #    TurnUsbOff(i_scan)
        #    TurnUsbOn(i_scan, TIME_USB_READY)

    TurnUsbOff(i_scan, TIME_AFTER_SCAN)
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
        + DISPLAY_FILE
    )
    # print(commandconv)
    WriteTimeLogfile("scanAcq: Start conversion jp2: " + commandconv)
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
    CurrentDateinS = DateToSeconds(date) + i_scan
    date = SecondsToDate(CurrentDateinS)
    scanner.LastImgTime = date
    # print("image time: ",scanner.LastImgTime)
    scanner.LastImgFile = imagepathjp2000
    WriteTimeLogfile("scanAcq: end")
    return scanner


def ScannerPreview(i_scan: int):
    image = f"{i_scan + 1}.jpg"
    error = TurnUsbOn(i_scan, TIME_USB_READY)
    if error != 0:
        Scanner.error = 1
        res = Scanner.error
        return image, res
    #### file = imagepath + image
    # On ne passe pas le device, car on n'allume qu'un port USB
    # donc scanimage va trouver le seul scanner sous tension !
    command = (
        "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage --mode="
        + Scanner.mode
        + " --resolution=75"
        + " --format=tiff >"
        + imagepathtiff
        + " | tee -a "
        + DISPLAY_FILE
        # ######: Il faudrait faire la conversion en JPEG !!!!
        #        + " --format=jpeg >"
        #        + file
    )
    WriteTimeLogfile("command:" + command)
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
    TurnUsbOff(i_scan)
    if res > 0:
        WriteTimeLogfile("error acquisition: " + result.stdout + result.stderr)
    else:
        WriteTimeLogfile("Preview OK")

    return image, res


def listScannerSerials():
    """Renvoie la liste des numéros de série des scanners

    Returns:
        list: les numéros de série des scanners
    """
    Scanner_ = ScannerData()
    listScannerconfigs_ = listConfigScanner()
    listserials = []

    for CurrentScanner_ in listScannerconfigs_:
        Scanner_.ReadScannerConfig(CurrentScanner_)
        serial = extract_serial(Scanner_.device)
        if serial:  # Only add non-empty serials
            listserials.append(serial)

    WriteTimeLogfile(listserials)
    return listserials


def listConfigScanner():
    try:
        # de la forme 1-Scanner.json
        listfile = [
            f for f in os.listdir(CONFIG_PATH) if re.match(r"[0-9]-Scanner.json", f)
        ]
        listfile.sort(reverse=False)
        WriteTimeLogfile(listfile)
    except OSError:
        listfile = ["1-Scanner.json", "2-Scanner.json", "3-Scanner.json"]
    return listfile


if __name__ == "__main__":
    # pylint: disable=duplicate-code
    InitGPIO()
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    listScannerSerials()
    scan_num = 0
    for CurrentScanner in listScannerconfigs:
        Scanner.ReadScannerConfig(CurrentScanner)
        print(Scanner.scanSearch(scan_num))
        Scanner.WriteScannerConfig(CurrentScanner)
        scan_num += 1

    if is_raspberry_pi():
        result_ = ScannerPreview(0)
        Scanner.LastImgFile = result_[0]
        Scanner.error = result_[1]

    # WriteScannerConfig(Scanner, "1-Scanner.json")
    sys.exit(0)
