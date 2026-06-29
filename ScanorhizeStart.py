#!/usr/bin/env python3
"""Lance le scanner et programme le prochain réveil
On gère les GPIO pour la carte 4G depuis ce programme
Si jamais il y a un plantage de TakePictures.py,
ce programme garde la main et éteint la clé 4G et le Raspberry Pi
"""

import sys
import time
from ConfigApp import is_debug, getLogger
from version import __version__
getLogger().info("============= START =============")
getLogger().info("ScanorhizeStart.py version: %s", __version__)

from subprocess import run, CalledProcessError, Popen
import argparse
from ConfigApp import getUsbDir
from pathlib import Path


from OSUtils import is_raspberry_pi
from WittyPy_utilities import is_reason_click
from WittyPy_utilities import (
    doShutdown,
    set_shutdown_time, get_shutdown_time,
    pre_shutdown_checks,
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
    calculate_next_wakeup_from_crontab,
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

# Etape 0 #############################################
getLogger().info("2 second delay... (Clock sync)")
time.sleep(2) # Clock sync



WITTYPI_TEST_FLAG = Path("wittypi_test_mode")

def isConfig():
    # WittyPi cycle test: flag file forces config mode for exactly one boot
    if WITTYPI_TEST_FLAG.exists():
        WITTYPI_TEST_FLAG.unlink()
        getLogger().warning("WITTYPI CYCLE TEST FLAG FOUND — STARTING IN CONFIG MODE")
        EndGPIO()
        return True
    # On regarde si on est en mode configuration
    config = not ReadGPIOConfig() or is_reason_click()  # 0 ou 1
    EndGPIO()
    return config


def setShutdownAndWakeUpDates():
    # Mise à jour des dates de réveil et d'arrêt du WittyPi
    # Car en développement, on peut dépasser la date de réveil
    # et dans ce cas, le WittyPi ne se reveille plus !
    # Idem si on change la batterie et qu'on repart quelques jours plus tard
    # On fait le calcul de la date de réveil systématiquement
    # avec la date courante.
    # Si la batterie est morte, l'heure sera aléatoire, il faut
    # refaire l'initialisation par le mode config, qui mettra
    # le boitier à l'heure correcte.
    return calculate_next_wakeup_from_crontab()


def createRunConfigFile():
    getLogger().info("On passe en mode config")    
    
    # On cree un fichier /run/config pour indiquer aux shells qu'on est en mode config
    cmd = "sudo touch /run/config >> Log/Scanorhize.log 2>&1"
    getLogger().info(cmd)
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
    getLogger().info("Lancement du point d'accès (192.168.4.1)")
    try:
        run("sudo nmcli con up hub_AP", shell=True, check=True)
        getLogger().info("AP activé")
    except Exception as e:
        getLogger().error("Echec activation AP : %s", e)
        
        
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
    getLogger().info(cmd)
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


def safeShutdown():
    from datetime import datetime, timedelta

    if is_debug():
        getLogger().warning("Dev mode: on ne lance pas le shutdown et on n'ejecte pas la clé")
        sys.exit(0)

    #Ensure mandatory register values before turning off board
    pre_shutdown_checks()

    cmdeject = "sudo eject /dev/sda"
    run(cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False)
    getLogger().info(cmdeject)

    # Force shutdown in 30s as a safety net if doShutdown() doesn't trigger
    stop_at = datetime.now() + timedelta(seconds=30)
    set_shutdown_time(stop_at.day, stop_at.hour, stop_at.minute, stop_at.second)
    readback = get_shutdown_time()
    getLogger().warning("Next stop at: %s (readback: %s)", stop_at.strftime("%d %H:%M:%S"), readback)

    if not is_raspberry_pi():
        getLogger().warning("Not a Raspberry Pi, so no poweroff")
        sys.exit(0)

    doShutdown()
    cmd = "sudo poweroff"
    getLogger().warning(cmd)
    run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)


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

def main():
    setShutdownAndWakeUpDates()
    config = isConfig()
    
    if config:
        getLogger().info("======= CONFIG MODE =======")
        launchServer()  #Launch web server in the background
        createRunConfigFile()
        initScanners()
    
    else: #Default mode
        getLogger().info("======= DEFAULT MODE =======")
        takePictures()
        
    #Update data from and to server
    #And, if not config mode, wait for pictures to upload
    if not getOffline():
        try:
            getLogger().info("==============")
            enable4G()
            getLogger().info("==============")
            updateDataFromAndToServer(configMode=config)
            getLogger().info("==============")
            
            #In default mode, wait for pictures to upload to server before shutting down
            if config == False:
                waitingForPicturesToUpload()
                safeShutdown()
        
        except Exception as e:
            getLogger().error(e)
         
    
    getLogger().info("End of ScanorhizeStart.py")
    if config:
        while True:
            time.sleep(60)
    else:
        sys.exit(0)


main()
