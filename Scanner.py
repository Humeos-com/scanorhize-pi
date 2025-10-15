#!/usr/bin/env python3
"""
Gestion des Scanners
"""

import os
from os import path
import sys
import json
from subprocess import run


from DateUtils import GetCurrentDate, DateToSeconds, SecondsToDate, CalculNextStartDate
from WittyPy_utilities import SetNextStartDate, setNextShutdownDate
from Miscellaneous import (
    InitGPIO,
    TurnUsbOn,
    TurnUsbOff,
    ReadBatVoltCap,
)
from OSUtils import is_raspberry_pi
from ConfigApp import (
    getDisplayFile,
    getConfigDir,
    getLogger,
    getImageDir,
    getThumbWidth,
    getThumbHeight,
)

X_MAX = 216
Y_MAX = 297
# Temps avant et après le scan pour les scanners Canon
TIME_BEFORE_SCAN_PIXMA = 40
TIME_AFTER_SCAN_PIXMA = 10
# Temps avant et après le scan pour les scanners Epson
TIME_BEFORE_SCAN_EPSON = 2
TIME_AFTER_SCAN_EPSON = 2

DISPLAY_FILE = getDisplayFile()
ResolutionList = ["75", "300", "600", "1200", "2400"]
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
        self.LastThumbFile = ""
        self.l = 0
        self.t = 0
        self.x = X_MAX
        self.y = Y_MAX
        self.x_max = X_MAX
        self.y_max = Y_MAX
        self.quality = 10
        self.device = "NoScannerDetected"
        self.token = "token_bidon"
        self.projectId = ""
        self.sampleId = ""
        self.UseServer = 1
        self.TimeBeforeScan = 0
        self.TimeAfterScan = 0
        self.error = 0
        self.enable = 0
        self.Campaign = "CampaignName"
        self.StartDate = "2025-01-01T08:00:00Z"
        self.PeriodeS = 3600

    def printScanner(self):
        for name, value in self.__dict__.items():
            print(f"{name}: {value}")

    def ReadScannerConfig(self, file=""):
        if file == "":
            if self.ScannerName == "":
                getLogger().error("ReadScannerConfig: ScannerName is empty")
                return self
            file = f"{self.ScannerName}.json"
        else:
            self.ScannerName = file.replace(".json", "")

        fullpath = os.path.join(getConfigDir(), file)
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)  # Load JSON into a dictionary
        except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
            getLogger().error("ReadScannerConfig: %s", e)
        else:
            self.__dict__.update(data)
        return self

    def WriteScannerConfig(self, file=""):
        if file == "":
            if self.ScannerName == "":
                getLogger().error("WriteScannerConfig: ScannerName is empty")
                return self
            file = f"{self.ScannerName}.json"
        else:
            self.ScannerName = file.replace(".json", "")

        fullpath = os.path.join(getConfigDir(), file)
        json_data = self.json()
        try:
            with open(fullpath, "w", encoding="utf-8") as outfile:
                outfile.write(json_data)
        except OSError as e:
            getLogger().error("WriteScannerConfig: OSError: %s", e)
            return 1

        return 0

    def is_pixma(self):
        """Renvoie True si le scanner est un Canon Pixma"""
        return self.device.startswith("pixma:")

    def is_epson(self):
        """Renvoie True si le scanner est un Epson"""
        return self.device.startswith("epsonscan2:")

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
        """Dump les paramètres du scanner au format JSON dans le fichier file
        c'est le fichier qui accompagne les images"""

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
        """Recherche le scanner et enregistre le numéro de série
        on regarde le port USB pour enregistrer le #serie du scanner

        "scanimage" renvoie toujour 0
        On utilise scanimage -f '%d' pour avoir uniquement le device !!!

        Soit il n'y a pas de scanner et on ne reçoit rien:
        ~/Scanorhize $ scanimage -f '%d'
        ~/Scanorhize $ echo $?
        0
        ~/Scanorhize $

        Soit il y a un scanner et on reçoit le message:
        ~/Scanorhize $ scanimage -f '%d'
        Pour les scanners Canon LIDE 400 ou LIDE 300, on reçoit:
        pixma:04A91912_43C7A6
        Pour les scanners Epson, on reçoit:
        epsonscan2:Epson Perfection V39II:XBZZ029435:esci2:usb:ES0283:319
        ~/Scanorhize $
        """

        getLogger().warning(
            "scanSearch: Starting scanner detection for port %d", i_scan + 1
        )
        error = TurnUsbOn(i_scan, 5)
        if error != 0:
            self.error = 1
            getLogger().warning("scanSearch: TurnUsbOn failed with error %d", error)
            return self

        res = 1
        # attribut par défaut si on ne trouve rien
        scanimage_message = "No scanners were identified"
        if is_raspberry_pi():
            command = f"scanimage -f '%d' " f"| tee -a {DISPLAY_FILE}"
            getLogger().warning("scanSearch: Executing command: %s", command)
            result = run(
                command,
                capture_output=True,
                universal_newlines=True,
                shell=True,
                check=False,
            )
            res = result.returncode
            scanimage_message = result.stdout
            getLogger().warning(
                "scanSearch: Command result - returncode: %d, stdout: '%s', stderr: '%s'",
                res,
                scanimage_message,
                result.stderr,
            )
            if len(scanimage_message) == 0:
                res = 1
                getLogger().warning(
                    "scanSearch: Empty scanimage output, setting res to 1"
                )
        else:
            # fake scanimage message
            res = 0
            scanimage_message = """pixma:00000_ABABAB"""
            getLogger().warning(
                "scanSearch: Using fake scanimage message: %s", scanimage_message
            )

        if res == 0 and len(scanimage_message.strip()) > 0:
            self.error = 0
            self.device = scanimage_message.strip()
            self.enable = 1
            getLogger().warning(
                "scanSearch: Scanner detected successfully - device: %s, enable: %d, error: %d",
                self.device,
                self.enable,
                self.error,
            )
        else:
            self.error = 1
            self.device = "NoScannerDetected"
            self.enable = 0
            self.UseServer = 0
            # On ne reinitalise pas tous les attributs car on peut être offline
            # self.projectId = ""
            # self.sampleId = ""
            # self.token = "token"
            getLogger().warning("scanSearch: No scanner detected")

        getLogger().warning("scanSearch: device %s", self.device)
        TurnUsbOff(i_scan, 0)
        if self.error > 0:
            getLogger().error("scanSearch: error: %s, %s", result.stdout, result.stderr)

        return self


def extract_serial(device_string: str) -> str:
    """Extract serial number from device string

    Args:
        device_string (str): Device string in format 'pixma:SERIAL' or
        epsonscan2:Epson Perfection V39II:SERIAL:esci2:usb:ES0283:319

    Returns:
        str: Serial number part after the colon, or empty string if invalid format
    """
    try:
        parts = device_string.split(":")
        if len(parts) > 1:
            if parts[0] == "epsonscan2":
                return parts[2] if len(parts) > 2 else ""

            return parts[1] if len(parts) > 1 else ""
        return ""
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
        "resolution4": ResolutionList[3],
        "resolution5": ResolutionList[4],
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
        "enable": scanner.enable,
        "error": scanner.error,
        "imagepathtiff": imagepathtiff,
        "imagepathjp2000": imagepathjp2000,
        "UseServer": scanner.UseServer,
        "Campaign": scanner.Campaign,
        "StartDate": scanner.StartDate,
        "PeriodeS": scanner.PeriodeS,
    }
    return Scannerparam


def generateThumbnail(
    jp2_path: str, thumb_path: str, original_width: float, original_height: float
) -> int:
    """Generate a thumbnail from JP2 image preserving aspect ratio

    Args:
        jp2_path: Path to the source JP2 image
        thumb_path: Path where the thumbnail will be saved
        original_width: Original image width (from scanner.x)
        original_height: Original image height (from scanner.y)

    Returns:
        int: 0 if success, error code otherwise
    """
    try:
        # Get thumbnail box dimensions from config
        th_x = getThumbWidth()
        th_y = getThumbHeight()

        # Calculate new dimensions preserving aspect ratio
        ratio = min(th_x / original_width, th_y / original_height)
        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        # Convert JP2 to JPEG with calculated dimensions
        command = (
            f"gdal_translate -of JPEG -outsize {new_width} {new_height} "
            f'-co "QUALITY=85" {jp2_path} {thumb_path}'
        )
        getLogger().warning("generateThumbnail: %s", command)

        result = run(
            command,
            capture_output=True,
            universal_newlines=True,
            shell=True,
            check=False,
        )

        if result.returncode != 0:
            getLogger().error(
                "generateThumbnail failed: %s %s", result.stdout, result.stderr
            )
            return result.returncode

        getLogger().warning(
            "Thumbnail generated: %sx%s -> %sx%s",
            original_width,
            original_height,
            new_width,
            new_height,
        )
        return 0

    except (OSError, ValueError, ZeroDivisionError) as e:
        getLogger().error("generateThumbnail error: %s", e)
        return 1


def scanAcq(scanner: ScannerData, i_scan: int, date: str):
    """Lance le scanimage et convertit l'image en jp2000
    cree également le fichier JSON avec les attributs de l'image
    et les paramètres du scanner

    Returns:
        _type_: _description_
    """
    if not scanner.enable:
        getLogger().warning("Scanner %s is disabled", str(i_scan + 1))
        return scanner

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
        f"scanimage {option_device} "
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
    scanner.LastImgFile = imagepathjp2000

    # Generate thumbnail from JP2
    fileName = date.replace(":", "-")
    thumbPath = path.join(getImageDir(), f"image_{fileName}_thumb.jpg")
    thumb_error = generateThumbnail(imagepathjp2000, thumbPath, scanner.x, scanner.y)
    if thumb_error == 0:
        scanner.LastThumbFile = thumbPath
        getLogger().warning("scanAcq: Thumbnail generated: %s", thumbPath)
    else:
        getLogger().warning(
            "scanAcq: Thumbnail generation failed, continuing without thumbnail"
        )
        scanner.LastThumbFile = ""

    getLogger().warning("scanAcq: end")

    return scanner


def ScannerPreview(scanner: ScannerData, i_scan: int):
    imagepreview = f"{getImageDir()}/{i_scan + 1}.jpg"
    error = TurnUsbOn(i_scan, scanner.TimeBeforeScan)
    if error != 0:
        scanner.error = 1
        res = scanner.error
        return imagepreview, res

    command = (
        f"scanimage "
        f"--mode={scanner.mode} "
        f"--resolution=75 "
        f"--format=jpeg > {imagepreview} | tee -a {DISPLAY_FILE}"
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
    TurnUsbOff(i_scan, scanner.TimeAfterScan)
    if res > 0:
        getLogger().error("error acquisition: " + result.stdout + result.stderr)
    else:
        getLogger().warning("Preview OK")

    return imagepreview, res


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
        else:
            listserials.append("")

    getLogger().warning(str(listserials))
    return listserials


def listConfigScanner():

    # Pour l'instant, on prend les 3 fichiers de configuration
    # try:
    #    # de la forme Scanner-[1-9].json
    #    listfile = [
    #        f for f in os.listdir(getConfigDir()) if re.match(r"^Scanner-[1-9].json$", f)
    #    ]
    #    listfile.sort(reverse=False)
    #    getLogger().warning(str(listfile))
    # except OSError:
    listfile = ["Scanner-1.json", "Scanner-2.json", "Scanner-3.json"]
    return listfile


def initScanners():
    """Operation à l'initialisation du Hub.
    Lorsqu'il n'y a aucun fichier de configuration.
    Brancher les scanners sur les ports USB et lancer
    l'initScanner. On va chercher les scanners sur les 3 ports
    et on va écrire leur configuration."""
    scanner = ScannerData()
    listScannerconfigs_ = ["Scanner-1.json", "Scanner-2.json", "Scanner-3.json"]
    i_scan = 0
    for CurrentScanner in listScannerconfigs_:
        scanner.ReadScannerConfig(CurrentScanner)
        scanner.scanSearch(i_scan)
        # Only set timing parameters if scanner was detected successfully
        if scanner.error == 0:
            scanner.TimeBeforeScan = (
                TIME_BEFORE_SCAN_PIXMA if scanner.is_pixma() else TIME_BEFORE_SCAN_EPSON
            )
            scanner.TimeAfterScan = (
                TIME_AFTER_SCAN_PIXMA if scanner.is_pixma() else TIME_AFTER_SCAN_EPSON
            )
            getLogger().warning("Scanner-%d: Scanner detected and enabled", i_scan + 1)
        else:
            getLogger().warning("Scanner-%d: No scanner detected, disabled", i_scan + 1)

        # Always write the configuration
        scanner.WriteScannerConfig(CurrentScanner)
        getLogger().warning("Scanner-%d: Configuration written", i_scan + 1)
        i_scan += 1
    if i_scan == 0:
        getLogger().warning("initScanners: Aucun scanner trouvé")


def calculate_and_set_next_date():
    """Calculate and set the next wake-up and shutdown date for the WittyPi.
    This function:
    1. Gets current date and calculates next start date for each enabled scanner
    2. Determines the earliest next start date
    3. Handles battery level considerations
    4. Sets the next wake-up and shutdown date
    """

    # Get current date and convert to seconds
    DateStart = GetCurrentDate()
    CurrentDateinS = DateToSeconds(DateStart)

    # Get list of scanner configs and initialize arrays dynamically
    listScannerconfigs_ = listConfigScanner()
    NextStartseconds = []
    NextStartDates = []

    # Calculate next start dates only for enabled scanners
    ScannerObj = ScannerData()
    for i_scan_, CurrentScanner_ in enumerate(listScannerconfigs_):
        ScannerObj.ReadScannerConfig(CurrentScanner_)
        nextDate, nextDateS = CalculNextStartDate(
            ScannerObj.StartDate, ScannerObj.PeriodeS, DateStart
        )
        # NextStartDates toujours présent dans la config
        NextStartDates.append(nextDate)
        getLogger().warning("Scanner-%s: Next start date: %s", i_scan_ + 1, nextDate)

        # On utilise NextStartseconds pour calcuer le prochain réveil
        if ScannerObj.enable:
            NextStartseconds.append(nextDateS)
        else:
            getLogger().warning(
                "Scanner-%s: Disabled, skipping for next wake up calculation",
                i_scan_ + 1,
            )

    # If no scanners are enabled, set a default wake-up time
    if not NextStartseconds:
        getLogger().warning("No enabled scanners found, setting default wake-up time")
        nextStartSecs = CurrentDateinS + (24 * 3600)  # 1 day from now
    else:
        # Calculate the next wake-up time
        # Ensure it's at least 600 seconds (10 minutes) from now
        nextStartSecs = max(int(min(NextStartseconds)), (CurrentDateinS + 600))

    nextStartDateValue_ = SecondsToDate(nextStartSecs)
    getLogger().warning("Next wake up at: %s", nextStartDateValue_)

    # Check battery level and adjust wake-up time if needed
    Bat = ReadBatVoltCap()
    if Bat[1] < 7:  # if battery is low, under 7%, delay wake-up by 30 days
        nextStartDateValue_ = SecondsToDate(nextStartSecs + (3600 * 24 * 30))
        getLogger().warning(
            "No more battery: wake up in 30 days: %s", nextStartDateValue_
        )

    # Set the next wake-up time
    SetNextStartDate(nextStartDateValue_)

    # Set shutdown time to 20 minutes from now as a safety measure
    StopTime = SecondsToDate(CurrentDateinS + (60 * 20))
    setNextShutdownDate(StopTime)
    return nextStartDateValue_


if __name__ == "__main__":
    # pylint: disable=duplicate-code
    InitGPIO()
    listScannerconfigs = listConfigScanner()
    listScannerSerials()
    initScanners()

    if is_raspberry_pi():
        Scanner = ScannerData()
        scan_num = 0  # on prend le premier
        Scanner.ReadScannerConfig(listScannerconfigs[scan_num])
        result_ = ScannerPreview(Scanner, scan_num)
        Scanner.LastImgFile = result_[0]
        Scanner.error = result_[1]

    sys.exit(0)
