"""
Gestion des Scanners
"""

import os
from os import path
import sys
import re
import json
from subprocess import run

from Miscellaneous import InitGPIO, TurnUsbOn, TurnUsbOff
from OSUtils import is_raspberry_pi
from ConfigApp import getDisplayFile, getConfigDir, getLogger, is_dev, getImageDir

X_MAX = 216
Y_MAX = 297
DISPLAY_FILE = getDisplayFile()
ResolutionList = ["300", "600", "1200"]
ColorList = ["Color", "Gray", "Lineart"]

imagepathtiff = path.join(getImageDir(), "imagescan.tiff")
imagepathjp2000 = path.join(getImageDir(), "imagejp2000.jp2")


class ScannerData:
    """
    Définition des paramètres du scanner
    """

    def __init__(self):
        self.ScannerName = ""
        self.mode = ColorList[0]
        self.resolution = ResolutionList[0]
        self.LastImgTime = ""
        self.LastImgFile = ""
        self.l = 0
        self.t = 0
        self.x = X_MAX
        self.y = Y_MAX
        self.x_max = X_MAX
        self.y_max = Y_MAX
        self.quality = 5
        self.device = "NoScannerDetected"
        self.token = "token_bidon"
        self.projectId = ""
        self.sampleId = ""
        self.UseServer = 0
        self.TimeBeforeScan = 0
        self.TimeAfterScan = 0
        self.error = 0
        self.Campaign = "CampaignName"
        self.StartDate = "2025-01-01T08:00:00Z"
        self.PeriodeS = 3600

    def printScanner(self):
        for name, value in self.__dict__.items():
            print(f"{name}: {value}")

    def ReadScannerConfig(self, file=""):
        fullpath = os.path.join(getConfigDir(), file)
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)  # Load JSON into a dictionary
        except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
            getLogger().error("ReadScannerConfig: %s", e)
        else:
            self.__dict__.update(data)
        finally:
            self.printScanner()
        return self

    def WriteScannerConfig(self, file):
        fullpath = os.path.join(getConfigDir(), file)
        json_data = self.json()
        try:
            with open(fullpath, "w", encoding="utf-8") as outfile:
                outfile.write(json_data)
        except OSError as e:
            getLogger().error("WriteScannerConfig: OSError: %s", e)
            return 1

        return 0

    def json(self):
        # Create a copy of the instance dictionary
        data_dict = self.__dict__.copy()
        return json.dumps(
            data_dict,
            default=lambda o: o.__dict__,
            sort_keys=True,
            ensure_ascii=False,
            indent=4,
        )

    def scanDumpMeta(self, file: str):
        """Dump les paramètres du scanner au format JSON dans le fichier file"""

        data = {
            "resolution": self.resolution,
            "quality": self.quality,
            "mode": self.mode,
            "l": self.l,
            "t": self.t,
            "x": self.x,
            "y": self.y,
        }
        json_data = json.dumps(
            data,
            default=lambda o: o.__dict__,
            sort_keys=False,
            ensure_ascii=False,
            indent=4,
        )
        try:
            with open(file, "w", encoding="utf-8") as outfile:
                outfile.write(json_data)
        except OSError as e:
            getLogger().error("scanDumpMeta: OSError: %s", e)
            return 1

        return 0

    def scanSearch(self, i_scan: int):
        # function to find scanner with sane
        # on cherche le scanners pour enregistrer le nom du device
        error = TurnUsbOn(i_scan, self.TimeBeforeScan)
        if error != 0:
            self.error = 1
            return self

        res = 1
        i = 0
        scanimage_message = "No scanners were identified"
        if is_raspberry_pi():
            cmd = (
                f"sudo LD_LIBRARY_PATH=/usr/local/lib scanimage -L "
                f"| tee -a {DISPLAY_FILE}"
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
        print("Scanner: ", self.device)
        TurnUsbOff(i_scan)
        if self.error > 0:
            getLogger().error("error acquisition: %s, %s", result.stdout, result.stderr)

        return self


# Initialisation de l'objet Scanner
# Scanner = ScannerData()


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
        "l": scanner.l,
        "t": scanner.t,
        "x": scanner.x,
        "y": scanner.y,
        "x_max": scanner.x_max,
        "y_max": scanner.y_max,
        "quality": scanner.quality,
        "device": scanner.device,
        "token": scanner.token,
        "TimeBeforeScan": scanner.TimeBeforeScan,
        "TimeAfterScan": scanner.TimeAfterScan,
        "projectId": scanner.projectId,
        "sampleId": scanner.sampleId,
        "error": scanner.error,
        "imagepathtiff": imagepathtiff,
        "imagepathjp2000": imagepathjp2000,
        "UseServer": scanner.UseServer,
        "Campaign": scanner.Campaign,
        "StartDate": scanner.StartDate,
        "PeriodeS": scanner.PeriodeS,
    }
    return Scannerparam


def scanAcq(scanner: ScannerData, i_scan: int, date: str):
    """Lance le scanimage et convertit l'image en jp2000
    cree également le fichier JSON avec les attributs de l'image
    et les paramètres du scanner

    Returns:
        _type_: _description_
    """

    getLogger().warning("scanAcq: on allume le port USB: %s", i_scan + 1)
    error = TurnUsbOn(i_scan, scanner.TimeBeforeScan)
    if error != 0:
        scanner.error = 1
        return scanner

    if scanner.device == "NoScannerDetected":
        option_device = ""
    else:
        option_device = f" --device={scanner.device}"
    # On n'utilise pas le device pour l'instant, car sinon, il faut respecter le cablage...
    option_device = ""
    command = (
        f"sudo LD_LIBRARY_PATH=/usr/local/lib scanimage {option_device} "
        f"--mode={scanner.mode} "
        f"--resolution={scanner.resolution} "
        f"-l {scanner.l} "
        f"-t {scanner.t} "
        f"-x {scanner.x} "
        f"-y {scanner.y} "
        f"--format=tiff > {imagepathtiff} | tee -a {DISPLAY_FILE}"
    )
    getLogger().warning("scanAcq: %s", command)
    res = 1
    i = 0
    while res != 0 and i < 2:
        # print("i=",i)
        getLogger().warning("scanAcq: try %s", i + 1)
        if is_raspberry_pi():
            result = run(
                command,
                capture_output=True,
                universal_newlines=True,
                shell=True,
                check=False,
            )
            getLogger().warning("scanAcq: result %s", result)
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
        #    TurnUsbOn(i_scan, scanner.TimeBeforeScan)
    # On a un timer de manière à ce que le charriot des Canon LIDE 400
    # revienne à la position de départ
    TurnUsbOff(i_scan, scanner.TimeAfterScan)
    if scanner.error > 0:
        getLogger().error("error acquisition: " + result.stdout + result.stderr)
        return scanner

    scanner.quality = min(scanner.quality, 90)

    commandconv = (
        f'gdal_translate -of JP2OpenJPEG -co "QUALITY={scanner.quality}" '
        f"{imagepathtiff} "
        f"{imagepathjp2000} | tee -a {DISPLAY_FILE}"
    )
    # print(commandconv)
    getLogger().warning("scanAcq: Start conversion jp2: %s", commandconv)
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
        getLogger().error("Error conversion jp2")
        scanner.error = 20
        return scanner

    getLogger().warning("scanAcq: End conversion jp2")
    scanner.LastImgTime = date
    # print("image time: ",scanner.LastImgTime)
    scanner.LastImgFile = imagepathjp2000
    getLogger().warning("scanAcq: end")

    return scanner


def ScannerPreview(scanner: ScannerData, i_scan: int):
    image = f"{i_scan + 1}.jpg"
    error = TurnUsbOn(i_scan, scanner.TimeBeforeScan)
    if error != 0:
        scanner.error = 1
        res = scanner.error
        return image, res
    #### file = imagepath + image
    # On ne passe pas le device, car on n'allume qu'un port USB
    # donc scanimage va trouver le seul scanner sous tension !
    # ######: Il faudrait faire la conversion en JPEG !!!!
    #        + " --format=jpeg >"
    #        + file
    command = (
        f"sudo LD_LIBRARY_PATH=/usr/local/lib scanimage "
        f"--mode={scanner.mode} "
        f"--resolution=75 "
        f"--format=tiff > {imagepathtiff} | tee -a {DISPLAY_FILE}"
    )
    getLogger().warning("Command: %s", command)
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
        getLogger().error("error acquisition: " + result.stdout + result.stderr)
    else:
        getLogger().warning("Preview OK")

    return image, res


def listScannerSerials():
    """Renvoie la liste des numéros de série des scanners

    Returns:
        list: les numéros de série des scanners
    """
    scanner = ScannerData()
    listScannerconfigs_ = listConfigScanner()
    listserials = []

    for CurrentScanner_ in listScannerconfigs_:
        scanner.ReadScannerConfig(CurrentScanner_)
        serial = extract_serial(scanner.device)
        if serial:  # Only add non-empty serials
            listserials.append(serial)

    getLogger().warning(str(listserials))
    return listserials


def listConfigScanner():
    try:
        # de la forme 1-Scanner.json
        listfile = [
            f for f in os.listdir(getConfigDir()) if re.match(r"[0-9]-Scanner.json", f)
        ]
        listfile.sort(reverse=False)
        getLogger().warning(str(listfile))
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
        if not is_dev():
            Scanner.WriteScannerConfig(CurrentScanner)
        scan_num += 1

    if is_raspberry_pi():
        result_ = ScannerPreview(Scanner, 0)
        Scanner.LastImgFile = result_[0]
        Scanner.error = result_[1]

    # WriteScannerConfig(Scanner, "1-Scanner.json")
    sys.exit(0)
