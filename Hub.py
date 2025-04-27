"""
Gestion du Hub et communication avec la plateforme Web
C'est le Hub qui synchronise les fichiers images et JSON sur le serveur
"""

import os
from os import path
from subprocess import run, SubprocessError, CalledProcessError
import json
from ConfigApp import (
    getConfigHubFile,
    getScanorhizeServer,
    getConnectTimeout,
    getMaxTime,
    getLogger,
    getS3Bucket,
    getConfigDir,
)
from Campaign import getUsbDir, USBSpace
from Miscellaneous import ReadBatVoltCap, pingAPI
from OSUtils import get_os, get_model, is_raspberry_pi
from Scanner import ScannerData, listConfigScanner, listScannerSerials
from AuthUtils import getHwAddr
from WittyPython import ReadTemp


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
        self.batteryLevelPercent: int = 0
        self.diskSpacePercent: int = 0
        self.temperature: float = 0

        self.initialized = True  # Mark as initialized
        self.ReadConfig()
        self.macAddress = getHwAddr()
        self.model = get_model()

    def json(self):
        """Convert object to JSON, excluding special attributes"""
        data = {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_") and key != "initialized"
        }
        return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=4)

    def WriteConfig(self):
        """Save the current configuration to a JSON file."""
        json_data = self.json()
        try:
            with open(getConfigHubFile(), "w", encoding="utf-8") as outfile:
                outfile.write(json_data)
                return 0
        except OSError as e:
            getLogger().error("save_config: OSError: %s", e)
            return 1

    def ReadConfig(self):
        fullpath = getConfigHubFile()
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)  # Load JSON into a dictionary
        except (FileNotFoundError, ValueError):
            getLogger().error("No file: %s", fullpath)
        else:
            self.__dict__.update(data)
        return self

    def print(self):
        """Prints the current configuration."""
        print("Current Configuration:")
        for key, value in self.__dict__.items():
            if key != "initialized":
                print(f"{key}: {value}")


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
    cmd = f"s3cmd --no-preserve --no-check-md5 --quiet sync {src} {getS3Bucket()}"
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
            Hub_.WriteConfig()

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
                    return 1
        return 0

    except (IndexError, ValueError, json.JSONDecodeError, KeyError) as e:
        getLogger().error("getTokens: Error parsing response: %s", e)
        return 1


def ReadScannerConfigFromServer(ScannerObj: ScannerData):
    hub_id = getHubId()
    cmdRead = f"s3cmd --no-preserve sync s3://hub-{hub_id}/home/pi/Scanorhize/{getConfigDir()}/{ScannerObj.ScannerName}.json {getConfigDir()}/{ScannerObj.ScannerName}.json"
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
    cmdWrite = f"s3cmd --no-preserve sync {getConfigDir()}/{ScannerObj.ScannerName}.json s3://hub-{hub_id}/home/pi/Scanorhize/{getConfigDir()}/{ScannerObj.ScannerName}.json"
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
    cmdRead = f"s3cmd --no-preserve sync s3://hub-{hub_id}/home/pi/Scanorhize/{getConfigHubFile()} {getConfigHubFile()}"
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
    cmdWrite = f"s3cmd --no-preserve sync {getConfigHubFile()} s3://hub-{hub_id}/home/pi/Scanorhize/{getConfigHubFile()} "
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
    json_data = {
        "batteryLevelPercent": Hub_.batteryLevelPercent,
        "temperatureCelsius": Hub_.temperature,
        "availableMemoryGB": Hub_.diskSpacePercent,
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
    else:
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


if __name__ == "__main__":
    # pylint: disable=duplicate-code
    getTokens()
    print(pingAPI("www.google.com"))
    # print(pingAPI("192.168.73.1"))
    # syncImageFiles()
    Hub = HubData()
    # Hub_.ReadConfig()
    volt, Hub.batteryLevelPercent = ReadBatVoltCap()
    Hub.diskSpacePercent = USBSpace()[0] / 1000
    Hub.temperature = ReadTemp()
    Hub.WriteConfig()
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
