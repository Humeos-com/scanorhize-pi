"""
Fonctions qui encapsulent l'API du serveur Web
"""

import os
from subprocess import run, SubprocessError
import json
from Miscellaneous import WriteTimeLogfile
from Campaign import RemoveTempImage, CreateTempImage
from OSUtils import get_os
from Scanner import ScannerData, listConfigScanner

SCANORIZE_SERVER = "scan.arditi.net"
CONFIG_PATH = "ConfigFile/Scanner"
CONNECT_TIMEOUT = 10  # Temps d'attente pour la connexion au serveur
MAX_TIME = 300  # Temps max pour faire le POST


class ServerData:
    """Gestion des paramètres de la carte SIM"""

    def __init__(self):
        self.apn = ""
        self.user = ""
        self.password = ""
        self.address = ""
        self.ping = 0

    def print(self):
        print("APN: ", self.apn)
        print("User: ", self.user)
        print("Password: ", self.password)
        print("Address: ", self.address)
        print("Ping: ", self.ping)

    def WriteConfig(self):
        with open(
            os.path.join(CONFIG_PATH, "Server.json"), "w", encoding="utf-8", indent=""
        ) as f:
            json.dump(self.__dict__, f)

    def ReadConfig(self):
        with open(os.path.join(CONFIG_PATH, "Server.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            if "apn" in data:
                self.apn = data["apn"]
            if "user" in data:
                self.user = data["user"]
            if "password" in data:
                self.password = data["password"]
            if "address" in data:
                self.address = data["address"]
            if "ping" in data:
                self.ping = data["ping"]


def updateServer(server: ServerData):
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


def ReadConfigFromServer(ScannerObj: ScannerData):
    cmdRead = f'curl --connect-timeout {CONNECT_TIMEOUT} --max-time {MAX_TIME} \
-X GET "https://{SCANORIZE_SERVER}/api/scanner/configuration" \
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
    cmdPost = f'curl --connect-timeout {CONNECT_TIMEOUT} --max-time {MAX_TIME} \
-X POST "https://{SCANORIZE_SERVER}/api/scanner/configuration" \
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

    cmdPost = f'curl --connect-timeout {CONNECT_TIMEOUT} --max-time {MAX_TIME} \
-X POST "https://{SCANORIZE_SERVER}/api/scanner/image" \
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


def SendParameters(battery, diskspace, temperature):
    # print(battery,diskspace,temperature)
    token = "G2IGG0eedSxemoWkMeZ9p4v_I1UCvKYXkV5ObWc8ErYLNXiiPM_g5xE3qNsFMW5wLhq4YK1SmR4b19Vn66qLyA"
    cmdPUT = f'curl --connect-timeout {CONNECT_TIMEOUT} --max-time {MAX_TIME} \
-X PUT "https://{SCANORIZE_SERVER}/api/scanner/state?\
battery={battery}&diskSpace={diskspace}&temperature={temperature}" \
-H "accept: */*" -H "scanner: {token}"'
    WriteTimeLogfile(cmdPUT)
    result = run(
        cmdPUT, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    # print(result.returncode, result.stdout, result.stderr)
    if result.returncode != 0:
        WriteTimeLogfile(
            "Put: return: " + str(result.returncode) + " error: " + result.stderr
        )
    else:
        if result.stdout.strip():  # Check if stdout is not empty
            results = json.loads(result.stdout)
            if results["status"] != 200:  # 200 = OK
                WriteTimeLogfile(
                    f"Put error: {results['status']}: {results['message']}"
                )
    return 0


def GetWifiSSID():
    cmd = "sudo iwgetid"
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        # print(result.returncode, result.stdout, result.stderr)
        x = (result.stdout).split('"')
    except SubprocessError as e:
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
    try:
        response = os.system("ping -c 1 " + address)
        # print("address: ",address,"response : ",response)
    except OSError as e:
        WriteTimeLogfile(f"Ping Error: {e}")
        response = 1
    if response == 0:
        print("Ping OK")
        return 1
    return 0


if __name__ == "__main__":
    # pylint: disable=duplicate-code
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    scan_num = 0
    for CurrentScanner in listScannerconfigs:
        Scanner.ReadScannerConfig(CurrentScanner)
        PostImageToServer(Scanner)
        scan_num += 1

    # WriteScannerConfig(Scanner, "1-Scanner.json")
