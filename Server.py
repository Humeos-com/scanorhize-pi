"""
    Fonctions qui encapsulent l'API du serveur Web
"""

import os
from subprocess import run, SubprocessError
import json
from Miscellaneous import WriteTimeLogfile
from Campaign import RemoveTempImage, CreateTempImage
from OSUtils import get_os

SCANORIZE_SERVER = "scan.arditi.net"


def CopyFromJson(Scanner, data):
    if "name" in data:
        Scanner.Campaign = data["name"]
    if "startDate" in data:
        Scanner.StartDate = data["startDate"]
    if "periode" in data:
        Scanner.PeriodeS = data["periode"]
    if "mode" in data:
        Scanner.mode = data["mode"]
    if "t" in data:
        Scanner.ZoneAcq.t = data["t"]
    if "l" in data:
        Scanner.ZoneAcq.l = data["l"]
    if "x" in data:
        Scanner.ZoneAcq.x = data["x"]
    if "y" in data:
        Scanner.ZoneAcq.y = data["y"]
    if "resolution" in data:
        Scanner.resolution = data["resolution"]
    if "quality" in data:
        Scanner.quality = data["quality"]
    return Scanner


def ReadConfigFromServer(Scanner):
    cmdRead = (
        'curl --max-time 60 -X GET "https://'
        + SCANORIZE_SERVER
        + '/api/scanner/configuration" -H "accept: application/json" -H "scanner:'
        + Scanner.token
        + '"'
    )
    print(cmdRead)
    result = run(
        cmdRead, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    print(result.returncode, result.stdout, result.stderr)
    if (result.returncode) == 0:
        try:
            data = json.loads(result.stdout)
            WriteTimeLogfile("Config server: " + result.stdout)
            CopyFromJson(Scanner, data)
            WriteTimeLogfile("json recu : " + data)
        except AttributeError as e:
            WriteTimeLogfile("Error reading json, error: " + str(e))
    else:
        WriteTimeLogfile("Config server error: " + result.stderr)
    return Scanner


def PostImageToServer(Scanner):
    error = 0
    Date = Scanner.LastImgTime
    Resolution = Scanner.resolution
    token = Scanner.token
    ImagePath = CreateTempImage(Scanner)
    cmdPost = (
        'sudo curl --max-time 60 -X POST "https://'
        + SCANORIZE_SERVER
        + '/api/scanner/image" -H "accept: */*" -H "scanner: '
        + token
        + '" -H "Content-Type: multipart/form-data" -F "date='
        + Date
        + '" -F "dpi='
        + str(Resolution)
        + '" -F "file=@'
        + ImagePath
        + '"'
    )
    print(cmdPost)
    result = run(
        cmdPost, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    # print(result.returncode, result.stdout, result.stderr)
    if result.returncode != 0:
        WriteTimeLogfile(
            "Post return: "
            + str(result.returncode)
            + "stdout :"
            + str(result.stdout)
            + " error: "
            + str(result.stderr)
        )
        error = 1
    RemoveTempImage(ImagePath)
    return error


def SendParameters(Scanner, battery, diskspace, temperature):
    # print(battery,diskspace,temperature)
    token = Scanner.token
    cmdPUT = (
        'sudo curl --max-time 60 -X PUT "https://'
        + SCANORIZE_SERVER
        + "/api/scanner/state?battery="
        + str(battery)
        + "&diskSpace="
        + str(diskspace)
        + "&temperature="
        + str(temperature)
        + '"'
        + ' -H "accept: */*" -H "scanner: '
        + token
        + '"'
    )
    print(cmdPUT)
    result = run(
        cmdPUT, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    # print(result.returncode, result.stdout, result.stderr)
    if result.returncode != 0:
        WriteTimeLogfile(
            "Put return: " + str(result.returncode) + " error: " + result.stderr
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
        print(f"Ping Error: {e}")
        response = 1
    if response == 0:
        print("Ping OK")
        return 1
    return 0
