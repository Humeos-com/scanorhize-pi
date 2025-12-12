#!/usr/bin/env python3
"""
Gestion du Hub et communication avec la plateforme Web
C'est le Hub qui synchronise les fichiers images et JSON sur le serveur
"""

import os
import sys
from os import path
from subprocess import run, SubprocessError, CalledProcessError
import json
import random
import argparse
from version import __version__

from DateUtils import (
    calculate_next_cron_time,
    GetCurrentDate,
    DateToSeconds,
    SecondsToDate,
)
from ConfigApp import (
    getConfigHubFile,
    getScanorhizeServer,
    getLogger,
    getS3Bucket,
    getConfigDir,
    getLogDir,
)
from Campaign import getUsbDir, USBSpace
from OSUtils import get_model, is_raspberry_pi
from Scanner import ScannerData, listConfigScanner, listScannerSerials
from AuthUtils import getHwAddr
from WittyPy_utilities import (
    set_over_temperature_action,
    get_temperature,
    SetNextStartDate,
    setNextShutdownDate,
)
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
        if hasattr(self, "_initialized"):  # Skip if already initialized
            return

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
        # Envoyer uniquement les vignettes (pas les images JP2 ni les JSON)
        # Recommandé pour les hautes résolutions >= 600 dpi
        # Les JP2 et leurs JSON restent ensemble sur USB pour maintenir la cohérence
        self.send_thumbnails_only: bool = False
        # Action à faire si on dépasse la température
        # 0: None, 1: Shutdown, 2: Startup
        self.over_temperature_action: int = 1
        # Point de température à partir duquel on dépasse la température
        self.over_temperature_point: int = 68
        # Reverse tunnel SSH port pour la maintenance à distance
        # cette valeur est sauvegardee dans Hub.json.
        # Mais à l'usage, si on relance le Hub, le port n'est plus
        # utilisable. Donc on le met à jour après la lecture de la configuration.
        random.seed()
        self.ssh_port: int = 0  # Random port between 2223-2299
        # Modèle du Raspberry Pi
        self.model: str = ""
        # todo.sh to run ?
        # si self.todo = True, alors on va chercher le fichier todo.sh
        # et on va l'exécuter au réveil suivant
        self.todo: bool = False
        # version du hub
        self.version: str = __version__
        # Période d'acquisition commune à tous les scanners (format crontab)
        # Format: minute heure jour_mois mois jour_semaine
        # Exemple: "0 8 * * *" pour tous les jours à 8h
        self.acquisition_schedule: str = "0 8 * * *"

        self._initialized = True  # Mark as initialized
        self.read_config()

    def json(self):
        """Convert object to JSON, excluding special attributes"""
        data = {
            key: value
            for key, value in self.__dict__.items()
            # On ecrit toutes les valeurs dans le fichier de configuration Hub.json, par contre,
            # on en ignore lors de la lecture dans read_config()
            if not key.startswith("_")
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
            # On ne lit pas macAddress, model et ssh_port depuis le fichier
            filtered_data = {
                key: value
                for key, value in data.items()
                if key not in ("macAddress", "model", "ssh_port")
            }
            self.__dict__.update(filtered_data)

        # On initialise ces valeurs seulement si elles n'ont pas encore de valeur valide
        if self.macAddress == "00:00:00:00:00:00":
            self.macAddress = getHwAddr()
        if self.model == "":
            self.model = get_model()
        if self.ssh_port == 0:
            self.ssh_port = random.randint(2223, 2299)  # Random port between 2223-2299

        set_over_temperature_action(
            self.over_temperature_action, self.over_temperature_point
        )
        self.version = __version__
        return self

    def print(self):
        """Prints the current configuration."""
        print("Current Configuration:")
        for key, value in self.__dict__.items():
            if key != "_initialized":
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


def getSendThumbnailsOnly():
    return HubData().send_thumbnails_only


def getOverTemperatureAction():
    return HubData().over_temperature_action


def getOverTemperaturePoint():
    return HubData().over_temperature_point


def getSSHPort():
    return HubData().ssh_port


def TodoEnabled():
    return HubData().todo


def setTodo(todo: bool):
    HubData().todo = todo
    HubData().write_config()


def getTodo():
    if TodoEnabled():
        # Download todo.sh from s3
        hub_id = getHubId()
        cmd = f"s3cmd --no-preserve sync s3://hubs/hub-{hub_id}/home/pi/todo.sh ../todo.sh"
        getLogger().warning(cmd)
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=False
        )
        if result.returncode != 0:
            getLogger().error(
                "Failed to download todo.sh: return code: %s, %s",
                result.returncode,
                result.stderr,
            )
            return 1
        getLogger().warning("todo.sh downloaded successfully")
    return 0


def getAcquisitionSchedule():
    return HubData().acquisition_schedule


def getUseServer():
    return HubData().use_server


def getHubId():
    hub_id = HubData().macAddress.replace(":", "")
    if hub_id == "":
        getLogger().error("getHubId: macAddress is empty")
    return hub_id


def remove_image_files(folder: str, thumbnails_only: bool = False):
    """Remove image files from directory

    Args:
        folder: Directory to clean
        thumbnails_only: If True, remove only thumbnails.
                        If False, remove all (JP2, JSON, thumbnails)
    """
    if not os.path.exists(folder):
        return
    for root, _, files in os.walk(folder, topdown=False):
        for name in files:
            should_remove = False

            if thumbnails_only:
                # Only remove thumbnails (files with 'thumb' in name)
                if "thumb" in name and name.endswith(".jpg"):
                    should_remove = True
            else:
                # Remove all: JP2, JSON, and thumbnails
                if name.endswith((".jp2", ".json")) or (
                    "thumb" in name and name.endswith(".jpg")
                ):
                    should_remove = True

            if should_remove:
                file_path = os.path.join(root, name)
                try:
                    os.remove(file_path)
                    getLogger().warning("remove_image_files: removed %s", file_path)
                except (FileNotFoundError, PermissionError) as e:
                    getLogger().error("Error removing file %s: %s", file_path, e)


def syncImageFiles(hub_: HubData):
    """Synchronise les fichiers images et JSON sur le serveur"""
    src = path.join(getUsbDir(), hub_.projectId)

    # Build s3cmd command with optional filters for thumbnails only mode
    if hub_.send_thumbnails_only:
        # Only sync thumbnails (no JP2, no JSON)
        # JSON files stay with their JP2 on USB to maintain data consistency
        cmd = (
            f"s3cmd --include '*thumb*' --exclude '*' "
            f"--no-preserve --no-progress sync {src} {getS3Bucket()}"
        )
        getLogger().warning("Syncing thumbnails only (send_thumbnails_only=True)")
    else:
        # Sync all files (default behavior)
        cmd = f"s3cmd --no-preserve --no-progress sync {src} {getS3Bucket()}"
        getLogger().warning("Syncing all files (send_thumbnails_only=False)")

    getLogger().warning(cmd)
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        getLogger().warning("SyncImageFiles from %s: %s", src, result.stdout)
        # Remove only what was sent: thumbnails only or all files
        remove_image_files(src, thumbnails_only=hub_.send_thumbnails_only)
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("SyncImageFiles from %s: %s", src, e)


def syncLogFiles():
    """Synchronise les fichiers de logs sur S3"""
    log_dir = getLogDir()
    hub_id = getHubId()
    s3_log_path = f"s3://hubs/hub-{hub_id}/home/pi/Scanorhize/"

    cmd = f"s3cmd --no-preserve --no-progress sync {log_dir} {s3_log_path}"
    getLogger().warning("Syncing log files: %s", cmd)

    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        getLogger().warning("SyncLogFiles: %s", result.stdout)
        return 0
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("SyncLogFiles error: %s", e)
        return 1


def runTodo():
    """Run the todo.sh if it exists in the .. (/home/pi) directory and has execute permissions"""
    todo_path = "../todo.sh"

    # Check if file exists
    if not os.path.exists(todo_path):
        getLogger().warning("todo.sh not found at %s", todo_path)
        return

    # Check if file has execute permissions
    if not os.access(todo_path, os.X_OK):
        getLogger().error(
            "todo.sh exists but does not have execute permissions: %s", todo_path
        )
        try:
            # Try to add execute permissions
            os.chmod(todo_path, 0o755)
            getLogger().warning("Added execute permissions to todo.sh")
        except OSError as e:
            getLogger().error("Failed to add execute permissions to todo.sh: %s", e)
            return

    getLogger().warning("Run todo.sh")
    try:
        result = run(todo_path, shell=True, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            getLogger().warning("../todo.sh executed successfully")
            getLogger().warning("../todo.sh: %s", result.stdout)
        else:
            getLogger().error(
                "Failed to execute todo.sh: return code: %s, %s",
                result.returncode,
                result.stderr,
            )
    except CalledProcessError as exc:
        getLogger().error("Failed to execute todo.sh: %s", exc.stderr)
        return

    # Rename the file after successful execution
    try:
        os.rename(todo_path, "../todo.sh.done")
        getLogger().warning("todo.sh executed successfully and renamed to todo.sh.done")
    except OSError as e:
        getLogger().error("Failed to rename todo.sh to todo.sh.done: %s", e)


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
    SSID = "No SSID"
    if not is_raspberry_pi():
        return SSID
    cmd = "sudo iwgetid -r"
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        if result.returncode != 0:
            getLogger().info(
                "Error GetWifiSSID: return: %s error: %s",
                result.returncode,
                result.stderr,
            )
            return SSID
        SSID = result.stdout
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("Error GetWifiSSID: %s", e)
        return SSID

    return SSID


def GetIP():
    IP = "0.0.0.0"
    if not is_raspberry_pi():
        return IP
    cmd = "hostname -I"
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
        if result.returncode != 0:
            getLogger().error(
                "Error GetIP: return: %s error: %s", result.returncode, result.stderr
            )
            return IP
        x = (result.stdout).split()
        if not x:  # Check if list is empty
            getLogger().warning("GetIP: No IP address found in hostname -I output")
            return IP
        IP = x[0]
    except (SubprocessError, CalledProcessError) as e:
        getLogger().error("Error GetIP: %s", e)
        return IP

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
        get_temperature(),  # temperature
    ]


def calculate_next_wakeup_from_crontab():
    """Calcule et configure le prochain réveil WittyPi selon le crontab Hub

    Returns:
        str: Date du prochain réveil (ISO8601)
    """

    # Obtenir la date actuelle
    current_date = GetCurrentDate()
    current_date_s = DateToSeconds(current_date)

    # Lire le schedule crontab du Hub
    hub = HubData()
    hub.read_config()
    schedule = hub.acquisition_schedule

    # Calculer la prochaine exécution selon le crontab
    try:
        next_date, next_date_s = calculate_next_cron_time(schedule, current_date)
    except ValueError as e:
        getLogger().error("Invalid crontab schedule, using default 1h: %s", e)
        # Fallback: 1 heure plus tard
        next_date_s = current_date_s + 3600
        next_date = SecondsToDate(next_date_s)

    # Minimum 10 minutes à partir de maintenant
    next_date_s = max(next_date_s, current_date_s + 600)

    # Gérer batterie faible (< 3.5V -> +1 jour)
    battery = ReadBatVoltCap()
    if battery[0] < 3.5:
        # Stops the hub until battery is charged through the solar panel
        next_date_s = current_date_s + (3600 * 24 * 1)
        getLogger().warning("Low battery, delaying wakeup by 1 day")

    # Configurer le WittyPi
    next_date = SecondsToDate(next_date_s)
    SetNextStartDate(next_date)

    # Configurer shutdown 20 minutes après le démarrage actuel
    shutdown_time = SecondsToDate(current_date_s + (60 * 20))
    setNextShutdownDate(shutdown_time)

    getLogger().warning(
        "Next wakeup scheduled at: %s (from crontab: %s)", next_date, schedule
    )

    return next_date


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Hub.py",
        usage="%(prog)s [--version]",
        epilog="""Lance la synchronisation des fichiers images et JSON sur le serveur""",
    )
    # pylint: disable=duplicate-code
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
    print(f"macAddress: {Hub.macAddress}, model: {Hub.model}, ssh_port: {Hub.ssh_port}")
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

    print(f"macAddress: {Hub.macAddress}, model: {Hub.model}, ssh_port: {Hub.ssh_port}")
    SendHubConfigToServer()
    ReadHubConfigFromServer()
    print(f"macAddress: {Hub.macAddress}, model: {Hub.model}, ssh_port: {Hub.ssh_port}")

    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    scan_num = 0
    for CurrentScanner in listScannerconfigs:
        Scanner.ReadScannerConfig(CurrentScanner)
        Scanner.WriteScannerConfig(CurrentScanner)
        SendScannerConfigToServer(Scanner)
        ReadScannerConfigFromServer(Scanner)
        scan_num += 1
