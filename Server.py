"""
Fonctions qui encapsulent l'API du serveur Web
"""

import sys
from os import path
from dataclasses import dataclass, asdict
from subprocess import run, SubprocessError, CalledProcessError
import json
from ConfigApp import (
    getConfigHubFile,
    getScanorhizeServer,
    getConnectTimeout,
    getMaxTime,
    getLogger,
)
from Miscellaneous import WriteTimeLogfile
from Campaign import RemoveTempImage, CreateTempImage, getUsbDir
from OSUtils import get_os
from Scanner import ScannerData, listConfigScanner, listScannerSerials
from AuthUtils import getHwAddr


@dataclass
class HubData:
    """Gestion des paramètres du Raspberry et de la carte SIM"""

    apn: str = ""
    user: str = ""
    password: str = ""
    address: str = ""
    ping: int = 0
    projectId: str = ""
    token: str = "token_bidon"
    batteryLevelPercent: int = 0
    diskSpacePercent: int = 0
    temperature: float = 0

    def WriteConfig(self):
        fullpath = getConfigHubFile()
        try:
            with open(fullpath, "w", encoding="utf-8") as openfile:
                json.dump(
                    self.__dict__,
                    openfile,
                    sort_keys=True,
                    ensure_ascii=False,
                    indent=4,
                )
        except (FileNotFoundError, ValueError):
            WriteTimeLogfile(f"No file: {fullpath}")

    def ReadConfig(self):
        fullpath = getConfigHubFile()
        try:
            with open(fullpath, "r", encoding="utf-8") as openfile:
                data = json.load(openfile)  # Load JSON into a dictionary
        except (FileNotFoundError, ValueError):
            getLogger().error("No file: %s", fullpath)
        else:
            self.__dict__.update(data)
        finally:
            self.print()
        return self

    def print(self):
        """Print all dataclass attributes"""
        for name, value in asdict(self).items():
            print(f"{name}: {value}")


def updateServer(server: HubData):
    server_param = {
        "apn": server.apn,
        "user": server.user,
        "password": server.password,
        "address": server.address,
        "ping": server.ping,
    }
    return server_param


def CopyFromJson(ScannerObj: ScannerData, data):
    if "name" in data:
        ScannerObj.Campaign = data["name"]
    if "startDate" in data:
        ScannerObj.StartDate = data["startDate"]
    if "periode" in data:
        ScannerObj.PeriodeS = data["periode"]
    if "mode" in data:
        ScannerObj.mode = data["mode"]
    if "t" in data:
        ScannerObj.ZoneAcq.t = data["t"]
    if "l" in data:
        ScannerObj.ZoneAcq.l = data["l"]
    if "x" in data:
        ScannerObj.ZoneAcq.x = data["x"]
    if "y" in data:
        ScannerObj.ZoneAcq.y = data["y"]
    if "resolution" in data:
        ScannerObj.resolution = data["resolution"]
    if "quality" in data:
        ScannerObj.quality = data["quality"]
    return ScannerObj

def syncImageFiles(hub_: HubData):
    """Synchronise les fichiers images et JSON sur le serveur"""
    # On envoie les fichiers images
    # On envoie les fichiers JSON
    src = path.join(getUsbDir(), hub_.projectId)
    cmd = f"s3cmd sync {src} s3://scanorhize-images-prod"
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        getLogger().warning("SyncImageFiles from %s: %s", src, result.stdout)
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("SyncImageFiles: %s", e)



def getTokens():

    # Get list of scanner serials
    scanner_serials = listScannerSerials()

    # Create dictionary with port entries dynamically
    serial_dict = {}
    num_scan = 0
    for num_scan, serial in enumerate(scanner_serials, 1):
        serial_dict[f"port{num_scan}"] = serial
    # num_scan contient le nombre de scanners

    json_data = {"macAddress": getHwAddr(), "serialNumbers": serial_dict}

    cmdPost = f"""curl -i --connect-timeout {getConnectTimeout()} --max-time {getMaxTime()} \
-X POST "https://{getScanorhizeServer()}/auth/devices" \
-H "accept: */*" -H "Content-Type: application/json" \
--data '{json.dumps(json_data)}' """

    getLogger().warning(cmdPost)
    result = run(
        cmdPost, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode != 0:
        getLogger().error(
            "Post auth/devices: return: %s  error: %s", result.returncode, result.stderr
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

        getLogger().warning("Response status code: %s", status_code)

        if not 200 <= status_code < 300:
            getLogger().error("Error: HTTP %s", status_code)
            return 1

        if body.strip():
            results = json.loads(body)
            Hub_ = HubData()
            Hub_.ReadConfig()
            Hub_.token = results["accessTokenHub"]
            Hub_.projectId = results["projectId"]
            Hub_.WriteConfig()
            for i in range(1, num_scan + 1):
                # Initialisation de l'objet Scanner
                Scanner_ = ScannerData()
                Scanner_.ReadScannerConfig(f"{i}-Scanner.json")
                # On met à jour les valeurs
                Scanner_.token = results["accessTokenScanners"][f"port{i}"]
                Scanner_.projectId = results["projectId"]
                Scanner_.sampleId = results["sampleIds"][f"port{i}"]
                # On sauve le tout
                Scanner_.WriteScannerConfig(f"{i}-Scanner.json")
        return 0

    except (IndexError, ValueError, json.JSONDecodeError) as e:
        WriteTimeLogfile(f"getTokens: Error parsing response: {str(e)}")
        return 1


def ReadConfigFromServer(ScannerObj: ScannerData):
    cmdRead = f'curl --connect-timeout {getConnectTimeout()} --max-time {getMaxTime()} \
-X GET "https://{getScanorhizeServer()}/api/scanner/configuration" \
-H "accept: application/json" -H "scanner:{ScannerObj.token}"'
    print(cmdRead)
    result = run(
        cmdRead, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    print(result.returncode, result.stdout, result.stderr)

    if result.returncode != 0:
        WriteTimeLogfile(
            f"ReadConfigFromServer: return: {result.returncode} error: {result.stderr}"
        )
        error = 1
    else:
        try:
            if result.stdout.strip():  # Check if stdout is not empty
                results = json.loads(result.stdout)
                CopyFromJson(ScannerObj, results)
                error = 0
            else:
                # reponse vide
                WriteTimeLogfile("ReadConfigFromServer: aucune donnée reçue")
                error = 1
        except json.JSONDecodeError as e:
            WriteTimeLogfile(f"JSON decode error: {str(e)}")
            error = 1
        except AttributeError as e:
            WriteTimeLogfile(f"Error reading json, error: {str(e)}")
            error = 1

        if not error:
            WriteTimeLogfile("ReadConfigFromServer: OK")
    return ScannerObj


def SendConfigToServer(ScannerObj: ScannerData):
    cmdPost = f'curl --connect-timeout {getConnectTimeout()} --max-time {getMaxTime()} \
-X POST "https://{getScanorhizeServer()}/api/scanner/configuration" \
-H "accept: application/json" -H "scanner:{ScannerObj.token}" \
-H "Content-Type: application/json" \
-d {ScannerObj.json()}'
    WriteTimeLogfile(cmdPost)


def PostImageToServer(ScannerObj: ScannerData):
    error = 0
    Date = ScannerObj.LastImgTime
    Resolution = ScannerObj.resolution
    token = ScannerObj.token
    ImagePath = CreateTempImage(ScannerObj)

    cmdPost = f'curl -i --connect-timeout {getConnectTimeout()} --max-time {getMaxTime()} \
-X POST "https://{getScanorhizeServer()}/api/scanner/image" \
-H "accept: */*" -H "scanner: {token}" \
-H "Content-Type: multipart/form-data" \
-F "date={Date}" -F "dpi={Resolution}" \
-F "file=@{ImagePath}"'

    WriteTimeLogfile(cmdPost)
    result = run(
        cmdPost, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    # print(f"PostImageToServer: {result.returncode}, {result.stdout}, {result.stderr}")
    if result.returncode != 0:
        WriteTimeLogfile(
            f"PostImageToServer: return: {result.returncode} error: {result.stderr}"
        )
        error = 1
    else:
        try:
            if result.stdout.strip():  # Check if stdout is not empty
                results = json.loads(result.stdout)
                if results["status"] != 200:  # 200 = OK
                    WriteTimeLogfile(
                        f"Post error: {results['status']}: {results['message']}"
                    )
                    error = 1
            else:
                # reponse vide = reponse normale sur le post des images
                error = 0
        except json.JSONDecodeError as e:
            WriteTimeLogfile(f"JSON decode error: {str(e)}")
            error = 1
        except AttributeError as e:
            WriteTimeLogfile(f"Error reading json, error: {str(e)}")
            error = 1

        if not error:
            WriteTimeLogfile("PostImageToServer: OK")

    RemoveTempImage(ImagePath)
    return error


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

    WriteTimeLogfile(cmdPUT)
    result = run(
        cmdPUT, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode != 0:
        WriteTimeLogfile(
            f"Post hub-device: return: {result.returncode} error: {result.stderr}"
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

        WriteTimeLogfile(f"Response status code: {status_code}")

        if not 200 <= status_code < 300:
            WriteTimeLogfile(f"Error: HTTP {status_code}")
            return 1

        if body.strip():
            results = json.loads(body)
            if results["message"] == "Status updated":
                WriteTimeLogfile("Parameters sent to server: OK")
                return 0
            WriteTimeLogfile(f"Error: {results['message']}")
            return 1

    except (IndexError, ValueError, json.JSONDecodeError) as e:
        WriteTimeLogfile(f"SendParameters: Error parsing response: {str(e)}")
    return 1


def GetWifiSSID():
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


def pingAPI(address):
    """Lance un ping unique. Le timeout par défaut sur Linux est de 10s

    Args:
        address (str): nom DNS ou IP

    Returns:
        int: 1 si le address répond, 0 en cas d'erreur
    """
    try:
        run(["ping", "-c 1", address], capture_output=True, text=True, check=True)
        getLogger().warning("Ping OK: %s", address)
        return 1
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("Ping Error: %s", e)
    return 0


if __name__ == "__main__":
    # pylint: disable=duplicate-code
    getTokens()
    print(pingAPI("www.google.com"))
    # print(pingAPI("192.168.73.1"))
    # syncImageFiles()
    sys.exit(0)
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    scan_num = 0
    for CurrentScanner in listScannerconfigs:
        Scanner.ReadScannerConfig(CurrentScanner)
    #    PostImageToServer(Scanner)
        scan_num += 1

    # WriteScannerConfig(Scanner, "1-Scanner.json")
