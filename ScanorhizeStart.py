#!/usr/bin/env python3
"""Lance le scanner et programme le prochain réveil
On gère les GPIO pour la carte 4G depuis ce programme
Si jamais il y a un plantage de TakePictures.py,
ce programme garde la main et éteint la clé 4G et le Raspberry Pi
"""

import sys
import time
from datetime import datetime, timedelta, timezone

time.sleep(5)  # Wait for wp5d to sync the RTC to the system clock before anything else

import signal
from ConfigApp import getLogger

from version import __version__


from subprocess import run, CalledProcessError, Popen
import argparse
from ConfigApp import getUsbDir
from pathlib import Path


from WittyPy_utilities import (
    set_shutdown_time, get_shutdown_time,
    pre_shutdown_checks,
    setShutdownAndWakeUpDates,
    safeShutdown,
    is_mc_connected, WittyPi,
    REASON_CLICK_WP5, REASON_ALARM1_WP5, REASON_ALARM2_WP5,
    SetNextStartDate,
)
from Miscellaneous import (
    EndGPIO,
    enable4G,
    check_connectivity,
    ReadGPIOConfig,
)

from Scanner import (
    initScanners,
    listConfigScanner,
    ScannerData,
)
from Hub import (
    HubData,
    getTokens,
    SendParameters,
    ReadScannerConfigFromServer,
    SendScannerConfigToServer,
    getOffline,
    getSyncImages,
    SendHubConfigToServer,
    ReadHubConfigFromServer,
    get_hub_info,
    syncLogFiles,
    TodoEnabled,
    getTodo,
    setTodo,
    runTodo,
    GetWifiSSID,
    GetIP,
)


parser = argparse.ArgumentParser(
    prog="ScanorhizeStart.py",
    usage="%(prog)s [--version]",
    epilog="""Lance le scan des images""",
)
parser.add_argument(
    "-v",
    "--version",
    action="store_true",
    help="Affiche la version du programme",
)
# pylint: disable=duplicate-code
args = parser.parse_args()
if args.version:
    print(f"ScanorhizeStart.py version: {__version__}")
    sys.exit(0)

WITTYPI_TEST_FLAG = Path("wittypi_test_mode")

def get_startup_mode() -> str:
    """Returns 'config', 'default', or the startup reason string."""
    if WITTYPI_TEST_FLAG.exists():
        WITTYPI_TEST_FLAG.unlink()
        getLogger().warning("WITTYPI CYCLE TEST FLAG FOUND — STARTING IN CONFIG MODE")
        EndGPIO()
        return "config"

    wp = WittyPi()
    reason = wp.reason_click
    getLogger().info("Startup reason: %s", wp.startup_reason_str())

    if reason == REASON_CLICK_WP5 or not ReadGPIOConfig():
        mode = "config"
    elif reason in (REASON_ALARM1_WP5, REASON_ALARM2_WP5):
        mode = "default"
    else:
        mode = wp.startup_reason_str()

    EndGPIO()
    return mode



def createRunConfigFile():   
    # On cree un fichier /run/config pour indiquer aux shells qu'on est en mode config
    cmd = "sudo touch /run/config >> Log/Scanorhize.log 2>&1"
    getLogger().info("Create run config file")
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode == 0:
        getLogger().info("creation /run/config OK")
    else:
        getLogger().error("Failed to create /run/config: %s", result.stderr)



def launchServer():
    
    print("Launching server")
    
    #Activation de l'AP
    getLogger().info("Starting access point (192.168.4.1)")
    try:
        state = run("nmcli -g GENERAL.STATE con show hub_AP", shell=True, capture_output=True, text=True)
        if "activated" in state.stdout.lower():
            getLogger().info("AP already active, skipping restart")
        else:
            run("sudo nmcli con up hub_AP", shell=True, check=True)
            getLogger().info("AP activated")
    except Exception as e:
        getLogger().error("Failed to activate AP: %s", e)
        
        
    # A priori, même sans connectivité, on doit avoir le SSID Scanorhize et une IP
    getLogger().info("SSID: %s", GetWifiSSID().strip())
    getLogger().info("IP: %s", GetIP())

    #Launch server in the background
    try:
        Popen(["python3", "WebServer.py"])
    except Exception as e:
        print(f"Error: {e}")


def takePictures():
    # Si on n'est pas en mode config, on lance le scan des images
    # On execute le contenu du fichier TakePictures.py
    # On scanne les images et on les envoie à la plateforme Web
    # On ne lance pas avec l'import, car s'il y a une erreur, le programme s'arrête
    # import TakePictures
    cmd = "python3 TakePictures.py"
    getLogger().info("Take pictures")
    try:
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=True
        )
    except CalledProcessError as exc:
        getLogger().error(exc.stderr)


def updateDataFromAndToServer(configMode):
    # Mise à jour des paramètres
    Hub = HubData()
    Hub.read_config()
    # Wait 15 seconds for battery voltage to stabilize before reading
    time.sleep(15)
    hub_info = get_hub_info()
    
    getLogger().info(
        "Volts: %.2fV  Bat: %d%%  USB: %dMo %d%%  Temp: %.1f°C",
        hub_info[0],
        hub_info[1],
        hub_info[2],
        hub_info[3],
        hub_info[4],
    )
    if not getOffline():
        # Transfert des données
        try:
            # Teste la connectivité
            check_connectivity()
            has_internet = True
            getLogger().info("Internet OK !")

            # On lance un sous programme qui met à jour toutes les données sur la plateforme
            # On échange avec la plateforme Web pour envoyer les paramètres

            runTodo()
            # On recupère eventuellement le todo.sh
            if TodoEnabled():
                getTodo()
                setTodo(False)

            # On récupère les configs des scanners depuis la plateforme / le S3 ??
            # selon le flag Scanner.UseServer
            SendParameters(Hub)  ## Plutôt envoie les paramètres au S3 ??
            SendHubConfigToServer()
            
            #Synchronize log files with server
            syncLogFiles()
            
            if Hub.use_server:
                ReadHubConfigFromServer()

            # On recupère les configurations des Scanners en fonction de use_server
            # sauf qu'on n'écrase pas les 2 attributs LastImgFile et LastImgTime
            # qui sont déjà présents dans la classe ScannerData
            Scanner = ScannerData()
            if configMode == True:
                for CurrentScanner in listConfigScanner():
                    Scanner.ReadScannerConfig(CurrentScanner)
                    SendScannerConfigToServer(Scanner)
                getLogger().info("getTokens")
                getTokens()
            
            else: #If NOT config mode
                for CurrentScanner in listConfigScanner():
                    Scanner.ReadScannerConfig(CurrentScanner)
                    if Scanner.UseServer:
                        last_img_file_save = Scanner.LastImgFile
                        last_img_time_save = Scanner.LastImgTime
                        ReadScannerConfigFromServer(Scanner)
                        # Relecture de la nouvelle config
                        Scanner.ReadScannerConfig(CurrentScanner)
                        # On remet les 2 attributs LastImgFile et LastImgTime
                        # à leurs valeurs précédentes
                        Scanner.LastImgFile = last_img_file_save
                        Scanner.LastImgTime = last_img_time_save
                        Scanner.WriteScannerConfig(CurrentScanner)

        except RuntimeError as exc:
            getLogger().error(exc)

    # fin getOffline()



def waitingForPicturesToUpload():
    USBfolder = Path(getUsbDir())
    print(f"USB folder: {USBfolder}")
    while True:
        jsonCount = sum(1 for _ in USBfolder.rglob("*.json"))
        jpgCount = sum(1 for _ in USBfolder.rglob("*.jpg"))
        jp2Count = sum(1 for _ in USBfolder.rglob("*.jp2"))
        print(f".json count: {jsonCount}")
        print(f".jpg count: {jpgCount}")
        print(f".jp2 count: {jp2Count}")
        
        if jsonCount + jpgCount + jp2Count == 0:
            break
                    
        time.sleep(10)

_pre_shutdown_done = False


def _get_shutdown_reason() -> str:
    """Infer WP5 shutdown reason from I2C registers."""
    # Reg 14: high nibble = startup reason, low nibble = shutdown reason (WP5 spec)
    _SHUTDOWN_REASONS = {
        0x01: "WittyPi wake-up alarm",
        0x02: "WittyPi shutdown alarm",
        0x03: "WittyPi button clicked",
        0x04: "WittyPi VIN drops (low voltage)",
        0x05: "WittyPi VIN recovers",
        0x06: "WittyPi over temperature",
        0x07: "WittyPi below temperature",
        0x08: "WittyPi newly powered",
        0x09: "reboot",
        0x0A: "missed heartbeat",
        0x0B: "external shutdown",
        0x0C: "external reboot",
    }
    try:
        if not is_mc_connected():
            return "unknown (WP5 not connected)"
        action_reason = WittyPi().i2c_read_byte(14)  # I2C_ACTION_REASON_WP5
        shutdown_reason = action_reason & 0x0F        # low nibble
        return _SHUTDOWN_REASONS.get(shutdown_reason, f"unknown (0x{shutdown_reason:02X})")
    except Exception as e:
        return f"unknown (I2C error: {e})"


def _on_sigterm(sig, frame):
    # If systemd is not stopping the whole system, this is just a service restart — exit quietly
    try:        
        state = run(["systemctl", "is-system-running"], capture_output=True, text=True)
        if state.stdout.strip() != "stopping":
            getLogger().warning("SIGTERM received — Service restart")
            sys.exit(0)
    except Exception:
        pass

    # Actual system shutdown (WP5 alarm, button, low voltage, etc.)
    reason = _get_shutdown_reason()
    getLogger().info("POWERING OFF — reason: %s", reason)
    if not _pre_shutdown_done:
        try:
            pre_shutdown_checks()
        except Exception as e:
            getLogger().error("pre_shutdown_checks on SIGTERM: %s", e)

    getLogger().info("=========== POWER OFF ===========")
    sys.exit(0)

# Register before main() so unexpected shutdowns are always caught
signal.signal(signal.SIGTERM, _on_sigterm)


def main():
    getLogger().info("Code version: %s", __version__)

    mode = get_startup_mode()  # "config", "default", or "newly_powered"

    if mode == "default":
        getLogger().info("======= DEFAULT MODE =======")
    elif mode == "config":
        getLogger().info("======= CONFIG MODE =======")
    else:
        getLogger().info("======= %s MODE =======", mode.upper())

    #Set shutdown and wake-up dates
    setShutdownAndWakeUpDates()

    if mode == "default":
        takePictures()

    elif mode == "config":
        launchServer()
        createRunConfigFile()
        initScanners()

    else:
        wakeup = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:00Z")
        getLogger().warning("Unexpected startup reason — setting next wake-up in 1 day: %s", wakeup)
        SetNextStartDate(wakeup)
        safeShutdown()
        return

    #Update data from and to server
    if not getOffline():
        try:
            enable4G()
            updateDataFromAndToServer(configMode=(mode == "config"))

            #In default mode, wait for pictures to be uploaded (by another service) before shutting down
            if mode == "default":
                waitingForPicturesToUpload()
                global _pre_shutdown_done
                _pre_shutdown_done = True
                safeShutdown()

        except Exception as e:
            getLogger().error(e)

    if mode == "config":
        while True:
            time.sleep(60)
    else:
        sys.exit(0)


main()
