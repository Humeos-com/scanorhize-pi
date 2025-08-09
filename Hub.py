"""
Gestion du Hub et communication avec la plateforme Web
C'est le Hub qui synchronise les fichiers images et JSON sur le serveur
"""

import os
import sys
from os import path
from subprocess import run, SubprocessError, CalledProcessError
import json
import argparse
from version import __version__

from ConfigApp import (
    getConfigHubFile,
    getScanorhizeServer,
    getLogger,
    getS3Bucket,
    getConfigDir,
)
from Campaign import getUsbDir, USBSpace
from OSUtils import get_os, get_model, is_raspberry_pi
from Scanner import ScannerData, listConfigScanner, listScannerSerials
from AuthUtils import getHwAddr
from WittyPython import ReadTemp
from utils import write_json_to_file
from pin_config import DEFAULT_PIN_ARRAY
from Miscellaneous import ReadBatVoltCap


class HubData:
    """Gestion des paramètres du Raspberry et de la carte SIM"""

    _instance = None  # Class variable to store the single instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HubData, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the instance if not already initialized."""
        if hasattr(self, "initialized"):  # Skip if already initialized
            return

        self.ping: int = 0
        self.projectId: str = ""
        self.macAddress: str = "00:00:00:00:00:00"
        self.token: str = "token_bidon"
        # Configuration des ports USB
        self.PinArray = DEFAULT_PIN_ARRAY
        # Est-ce qu'on récupère la configuration depuis le serveur ?
        self.use_server: bool = True
        # Temps en secondes pour la connexion du s3cmd
        self.connect_timeout: int = 10
        # Temps en secondes pour la durée du s3cmd
        self.max_time: int = 300
        # Temps max en secondes entre
        self.delta_time: int = 300
        # Mode connecté ou offline (on n'alluma pas la 4G)
        self.offline: bool = False
        # On synchronise les images ou non
        # si self.offline = True, alors on ne synchronise pas les images
        self.sync_images: bool = True
        # todo.sh to run ?
        # si self.todo = True, alors on va chercher le fichier todo.sh
        # et on va l'exécuter au réveil suivant
        self.todo: bool = False
        # version du hub
        self.version: str = __version__

        self.initialized = True  # Mark as initialized
        self.read_config()

    def json(self):
        """Convert object to JSON, excluding special attributes"""
        data = {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_") and key != "initialized"
        }
        return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=4)

    def write_config(self):
        """Save the current configuration to a JSON file."""
        json_data = self.json()
        return write_json_to_file(getConfigHubFile(), json_data)

    def read_config(self):
        fullpath = getConfigHubFile()
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)  # Load JSON into a dictionary
        except (FileNotFoundError, ValueError):
            getLogger().error("No file: %s", fullpath)
        else:
            self.__dict__.update(data)
        # On ecrase toujours ces 2 valeurs
        self.macAddress = getHwAddr()
        self.model = get_model()
        self.version = __version__
        return self

    def print(self):
        """Prints the current configuration."""
        print("Current Configuration:")
        for key, value in self.__dict__.items():
            if key != "initialized":
                print(f"{key}: {value}")


def getConnectTimeout():
    return HubData().connect_timeout


def getMaxTime():
    return HubData().max_time


def getDeltaTime():
    return HubData().delta_time


def getOffline():
    return HubData().offline


def getSyncImages():
    return HubData().sync_images


def getTodo():
    return HubData().todo


def getUseServer():
    return HubData().use_server


def updateServer(server: HubData):
    server_param = {
        "ping": server.ping,
    }
    return server_param


def getHubId():
    hub_id = HubData().macAddress.replace(":", "")
    if hub_id == "":
        getLogger().error("getHubId: macAddress is empty")
    return hub_id


def remove_image_files(folder: str):
    """Remove .jp2 and .json files from directory"""
    if not os.path.exists(folder):
        return
    for root, _, files in os.walk(folder, topdown=False):
        for name in files:
            if name.endswith((".jp2", ".json")):
                file_path = os.path.join(root, name)
                try:
                    os.remove(file_path)
                    getLogger().warning("remove_image_files: removed %s", file_path)
                except (FileNotFoundError, PermissionError) as e:
                    getLogger().error("Error removing file %s: %s", file_path, e)


def syncImageFiles(hub_: HubData):
    """Synchronise les fichiers images et JSON sur le serveur"""
    src = path.join(getUsbDir(), hub_.projectId)
    cmd = f"s3cmd --no-preserve --no-progress sync {src} {getS3Bucket()}"
    getLogger().warning(cmd)
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        getLogger().warning("SyncImageFiles from %s: %s", src, result.stdout)
        remove_image_files(src)
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("SyncImageFiles from %s: %s", src, e)


def getTokens():
    # Get list of scanner serials
    scanner_serials = listScannerSerials()

    # Create dictionary with port entries dynamically
    serial_dict = {}
    num_scan = 0
    for num_scan, serial in enumerate(scanner_serials, 1):
        serial_dict[f"port{num_scan}"] = serial

    Hub_ = HubData()
    json_data = {"macAddress": Hub_.macAddress, "serialNumbers": serial_dict}

    cmdPost = f"""curl -i --connect-timeout {getConnectTimeout()} --max-time {getMaxTime()} \
-X POST "https://{getScanorhizeServer()}/auth/devices" \
-H "accept: */*" -H "Content-Type: application/json" \
--data '{json.dumps(json_data)}' """

    getLogger().warning(cmdPost)
    result = run(
        cmdPost,
        capture_output=True,
        universal_newlines=True,
        shell=True,
        check=False,
    )
    if result.returncode != 0:
        getLogger().error(
            "Post auth/devices: return: %s  error: %s",
            result.returncode,
            result.stderr,
        )
        return 1

    try:
        response_parts = result.stdout.split("\n\n", 1)
        headers = response_parts[0]
        body = response_parts[1] if len(response_parts) > 1 else ""

        status_line = headers.split("\n")[0]
        status_code = int(status_line.split()[1])

        getLogger().warning("Response status code: %s", status_code)

        if not 200 <= status_code < 300:
            getLogger().error("Error: HTTP %s", status_code)
            return 1

        if body.strip():
            results = json.loads(body)
            Hub_.token = results["accessTokenHub"]
            Hub_.projectId = results["projectId"]
            Hub_.write_config()

            for i in range(1, num_scan + 1):
                Scanner_ = ScannerData()
                Scanner_.ReadScannerConfig(f"Scanner-{i}.json")
                port_key = f"port{i}"
                if port_key in results["accessTokenScanners"]:
                    Scanner_.token = results["accessTokenScanners"][port_key]
                    Scanner_.projectId = results["projectId"]
                    Scanner_.sampleId = results["sampleIds"][port_key]
                    Scanner_.WriteScannerConfig(f"Scanner-{i}.json")
                else:
                    getLogger().error("Missing token for %s", port_key)
                    continue
        return 0

    except (IndexError, ValueError, json.JSONDecodeError, KeyError) as e:
        getLogger().error("getTokens: Error parsing response: %s", e)
        return 1


def ReadScannerConfigFromServer(ScannerObj: ScannerData):
    hub_id = getHubId()
    cmdRead = f"s3cmd --no-preserve sync s3://hubs/hub-{hub_id}/home/pi/Scanorhize/{getConfigDir()}/{ScannerObj.ScannerName}.json {getConfigDir()}/{ScannerObj.ScannerName}.json"
    getLogger().warning(cmdRead)
    result = run(
        cmdRead, capture_output=True, universal_newlines=True, shell=True, check=False
    )

    if result.returncode != 0:
        getLogger().error(
            "ReadScannerConfigFromServer: return: %s  error: %s",
            result.returncode,
            result.stderr,
        )
        return 1

    getLogger().warning("%s: ReadScannerConfigFromServer: OK", ScannerObj.ScannerName)
    return 0


def SendScannerConfigToServer(ScannerObj: ScannerData):
    hub_id = getHubId()
    cmdWrite = f"s3cmd --no-preserve sync {getConfigDir()}/{ScannerObj.ScannerName}.json s3://hubs/hub-{hub_id}/home/pi/Scanorhize/{getConfigDir()}/{ScannerObj.ScannerName}.json"
    getLogger().warning(cmdWrite)
    result = run(
        cmdWrite, capture_output=True, universal_newlines=True, shell=True, check=False
    )

    if result.returncode != 0:
        getLogger().error(
            "SendScannerConfigToServer: return: %s  error: %s",
            result.returncode,
            result.stderr,
        )
        return 1

    getLogger().warning("%s: SendScannerConfigToServer: OK", ScannerObj.ScannerName)
    return 0


def ReadHubConfigFromServer():
    hub_id = getHubId()
    cmdRead = f"s3cmd --no-preserve sync s3://hubs/hub-{hub_id}/home/pi/Scanorhize/{getConfigHubFile()} {getConfigHubFile()}"
    getLogger().warning(cmdRead)
    result = run(
        cmdRead, capture_output=True, universal_newlines=True, shell=True, check=False
    )

    if result.returncode != 0:
        getLogger().error(
            "ReadHubConfigFromServer: return: %s  error: %s",
            result.returncode,
            result.stderr,
        )
        return 1

    getLogger().warning("hub-%s: ReadHubConfigFromServer: OK", hub_id)
    return 0


def SendHubConfigToServer():
    hub_id = getHubId()
    cmdWrite = f"s3cmd --no-preserve sync {getConfigHubFile()} s3://hubs/hub-{hub_id}/home/pi/Scanorhize/{getConfigHubFile()} "
    getLogger().warning(cmdWrite)
    result = run(
        cmdWrite, capture_output=True, universal_newlines=True, shell=True, check=False
    )

    if result.returncode != 0:
        getLogger().error(
            "SendHubConfigToServer: return: %s  error: %s",
            result.returncode,
            result.stderr,
        )
        return 1

    getLogger().warning("hub-%s: SendHubConfigToServer: OK", hub_id)
    return 0


def SendParameters(Hub_: HubData):
    # print(battery,diskspace,temperature)
    hub_info = get_hub_info()
    json_data = {
        "batteryVoltage": hub_info[0],
        "batteryLevelPercent": hub_info[1],
        "temperatureCelsius": hub_info[4],
        "availableMemoryGB": hub_info[2],
        "diskUsagePercent": hub_info[3],
        "version": Hub_.version,
    }

    cmdPUT = f"""curl -i --connect-timeout {getConnectTimeout()} --max-time {getMaxTime()} \
-X PATCH "https://{getScanorhizeServer()}/hub-device" \
-H "Authorization: Bearer {Hub_.token}" \
-H "Content-Type: application/json" \
--data '{json.dumps(json_data)}' """

    getLogger().warning(cmdPUT)
    result = run(
        cmdPUT, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode != 0:
        getLogger().error(
            "SendParameters: return: %s error: %s", result.returncode, result.stderr
        )
        return 1

    # Parse headers and body from response
    try:
        response_parts = result.stdout.split("\n\n", 1)
        headers = response_parts[0]
        body = response_parts[1] if len(response_parts) > 1 else ""

        # Get status code from first line of headers
        status_line = headers.split("\n")[0]
        status_code = int(status_line.split()[1])

        getLogger().warning("SendParameters: status: %s", status_code)

        if not 200 <= status_code < 300:
            getLogger().error("SendParameters: error: %s", status_code)
            return 1

        if body.strip():
            results = json.loads(body)
            if results["message"] == "Status updated":
                getLogger().warning("SendParameters: OK")
                return 0
            getLogger().error("SendParameters: error: %s", results["message"])
            return 1

    except (IndexError, ValueError, json.JSONDecodeError) as e:
        getLogger().error("SendParameters: error: %s", e)
    return 1


def GetWifiSSID():
    if not is_raspberry_pi():
        return "No SSID"
    cmd = "sudo iwgetid"
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        # print(result.returncode, result.stdout, result.stderr)
        x = (result.stdout).split('"')
    except (SubprocessError, CalledProcessError) as e:
        print(f"Error: {e}")
        x = ["", "", ""]
    # print(x)
    SSID = x[1]
    # print(SSID)
    return SSID


def GetIP():
    if get_os() == "MacOS":
        cmd = "ipconfig getifaddr en13"
        return "192.168.2.20"

    cmd = "hostname -I"
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    # print(result.returncode, result.stdout, result.stderr)
    x = (result.stdout).split()
    # print(x)
    IP = x[0]
    print(IP)
    return IP


def get_hub_info():
    """Get current hub information including battery, USB space, and temperature.

    Returns:
        list: [voltage, battery_percent, usb_space_mb, usb_space_percent, temperature]
    """
    usb_space_info = USBSpace()
    battery_info = ReadBatVoltCap()
    return [
        battery_info[0],  # voltage
        battery_info[1],  # battery percent
        usb_space_info[0],  # USB space in MB
        usb_space_info[1],  # USB space percent
        ReadTemp(),  # temperature
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Hub.py",
        usage="%(prog)s [--version]",
        epilog="""Lance la synchronisation des fichiers images et JSON sur le serveur""",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Affiche la version du programme",
    )
    args = parser.parse_args()
    if args.version:
        print(f"Hub.py version: {__version__}")
        sys.exit(0)

    # pylint: disable=duplicate-code
    getTokens()
    # syncImageFiles()
    Hub = HubData()
    Hub.read_config()
    hub_info_ = get_hub_info()
    getLogger().warning(
        "Volts: %.2fV  Bat: %d%%  USB: %dMo %d%%  Temp: %.1f°C",
        hub_info_[0],
        hub_info_[1],
        hub_info_[2],
        hub_info_[3],
        hub_info_[4],
    )

    SendHubConfigToServer()
    ReadHubConfigFromServer()

    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    scan_num = 0
    for CurrentScanner in listScannerconfigs:
        Scanner.ReadScannerConfig(CurrentScanner)
        Scanner.WriteScannerConfig(CurrentScanner)
        SendScannerConfigToServer(Scanner)
        ReadScannerConfigFromServer(Scanner)
        scan_num += 1
