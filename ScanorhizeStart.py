#!/usr/bin/env python3
"""Lance le scanner et programme le prochain réveil
On gère les GPIO pour la carte 4G depuis ce programme
Si jamais il y a un plantage de ScanorhizeProcess.py,
ce programme garde la main et éteint la clé 4G et le Raspberry Pi
"""

import sys
from subprocess import run, CalledProcessError
import argparse

from OSUtils import is_raspberry_pi
from WittyPy_utilities import is_reason_click
from WittyPy_utilities import doShutdown, setNextShutdownDate
from Miscellaneous import (
    EndGPIO,
    enable4G,
    disable4G,
    check_connectivity,
    ReadGPIOConfig,
    sync_time,
)
from DateUtils import GetCurrentDate, SecondsToDate, DateToSeconds
from ConfigApp import is_debug, getLogger
from Scanner import (
    initScanners,
    listConfigScanner,
    ScannerData,
    calculate_and_set_next_date,
)
from Hub import (
    HubData,
    getTokens,
    SendParameters,
    syncImageFiles,
    ReadScannerConfigFromServer,
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
    getScanorhizeServer,
    getSSHPort,
)
from version import __version__

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
args = parser.parse_args()
if args.version:
    print(f"ScanorhizeStart.py version: {__version__}")
    sys.exit(0)

# Etape 0 #############################################
getLogger().warning("ScanorhizeStart.py version: %s", __version__)

# On regarde si on est en mode configuration
config = not ReadGPIOConfig() or is_reason_click()  # 0 ou 1
EndGPIO()

# Etape 1 #############################################
# Mise à jour des dates de réveil et d'arrêt du WittyPi
# Car en développement, on peut dépasser la date de réveil
# et dans ce cas, le WittyPi ne se reveille plus !
# Idem si on change la batterie et qu'on repart quelques jours plus tard
# On fait le calcul de la date de réveil systématiquement
# avec la date courante.
# Si la batterie est morte, l'heure sera aléatoire, il faut
# refaire l'initialisation par le mode config, qui mettra
# le boitier à l'heure correcte.
nextStartDateValue = calculate_and_set_next_date()


if config:
    getLogger().warning("On passe en mode config")

    # Run initScanners() to initialize scanners
    # Init Scanners before getting tokens, because this operation
    # can be completed without network
    # En plus, il faut faire l'init sans la 4G car sinon on dépasse la consommation
    # maximale de la carte WittyPi, surtout si la batterie est faible
    getLogger().warning("Start InitScanners")
    initScanners()
    getLogger().warning("End InitScanners")

    # En mode config on lance le serveur web Scanorhize et on quitte
    if enable4G():
        getLogger().warning("4G enabled")

    try:
        check_connectivity()
        has_internet = True
        getLogger().warning("Internet OK !")
        sync_time()
        runTodo()

        # On recupère eventuellement le todo.sh
        if TodoEnabled():
            getTodo()
            setTodo(False)

        SendHubConfigToServer()
        syncLogFiles()
        # On crée un tunnel SSH inverse pour la maintenance à distance
        cmd = f"ssh -fN -R {getSSHPort()}:localhost:22 debian@{getScanorhizeServer()}  -p 2222 -E Log/ssh.log"
        run(cmd, shell=True, capture_output=True, text=True, check=False)
        getLogger().warning(
            "Tunnel SSH inverse créé sur le port %d pour le serveur %s",
            getSSHPort(),
            getScanorhizeServer(),
        )
        getLogger().warning("getTokens")
        getTokens()

    except RuntimeError as exc:
        getLogger().error("No internet connection: %s", exc)

    # A priori, même sans connectivité, on doit avoir le SSID Scanorhize et une IP
    getLogger().warning("SSID: %s", GetWifiSSID())
    getLogger().warning("IP: %s", GetIP())

    # En principe, on éteint le Raspberry Pi depuis l'application Web Scanorhize.py
    cmd = "nohup python3 Scanorhize.py >> Log/Scanorhize.log 2>&1 &"
    getLogger().warning(cmd)
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode == 0:
        getLogger().warning("Scanorhize.py started successfully")
    else:
        getLogger().error("Failed to start Scanorhize.py: %s", result.stderr)

    # En mode config on désactive la connexion réseau qui passe par le port USB
    cmd = "nohup sudo ./Shut_connection.sh > /tmp/Shut_connection.log 2>&1 &"
    getLogger().warning(cmd)
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode == 0:
        getLogger().warning("Shut_connection.sh started successfully")
    else:
        getLogger().error("Failed to start Shut_connection.sh: %s", result.stderr)
    sys.exit(0)

# Etape 2 #############################################
# Si on n'est pas en mode config, on lance le scan des images
# On execute le contenu du fichier ScanorhizeProcess.py
# On scanne les images et on les envoie à la plateforme Web
# On ne lance pas avec l'import, car s'il y a une erreur, le programme s'arrête
# import ScanorhizeProcess
cmd = "python3 ScanorhizeProcess.py"
getLogger().warning(cmd)
try:
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=True
    )
except CalledProcessError as exc:
    getLogger().error(exc.stderr)


# Etape 3 #############################################
# Mise à jour des paramètres
Hub = HubData()
Hub.read_config()
hub_info = get_hub_info()

getLogger().warning(
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
        # On allume la clé 4G et on attend d'avoir le réseau
        enable4G()
        # Teste la connectivité
        check_connectivity()

        # On synchronise l'horloge de la carte WittyPi avec le serveur
        try:
            cmd = "sudo ./TimeSynchronisation.sh"
            getLogger().warning(cmd)
            result = run(
                cmd,
                capture_output=True,
                universal_newlines=True,
                shell=True,
                check=False,
            )
        except CalledProcessError as exc:
            getLogger().error(exc.stderr)

        # Etape 4 #############################################
        # On lance un sous programme qui met à jour toutes les données sur la plateforme
        # On échange avec la plateforme Web pour envoyer les images et les paramètres

        runTodo()
        # On recupère eventuellement le todo.sh
        if TodoEnabled():
            getTodo()
            setTodo(False)

        # On récupère les configs des scanners depuis la plateforme / le S3 ??
        # selon le flag Scanner.UseServer
        SendParameters(Hub)  ## Plutôt envoie les paramètres au S3 ??
        SendHubConfigToServer()
        if Hub.use_server:
            ReadHubConfigFromServer()

        # On peut travailler sans synchroniser les images si le réseau est mauvais
        # ou si les images sont trop grosses pour le réseau
        if getSyncImages():
            syncImageFiles(Hub)

        # On recupère les configuration des Scanners en fonction de use_server
        # sauf qu'on n'écrase pas les 2 attributs LastImgFile et LastImgTime
        # qui sont déjà présents dans la classe ScannerData
        Scanner = ScannerData()
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

    finally:
        # On éteint la clé 4G
        disable4G()
# fin getOffline()

# Etape 4 #############################################
# On éteint le Raspberry Pi et le WittyPi
if is_debug():  # Debug mode
    getLogger().warning(
        "Dev mode: on ne lance pas le shutdown et on n'ejecte pas la clé"
    )
    sys.exit(0)

cmdeject = "sudo eject /dev/sda"
result = run(
    cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
)
getLogger().warning(cmdeject)

# On fixe l'heure d'arrêt dans 30 secondes,
# car des fois le Witty ne s'eteint pas sur le doShutdown()
date_now = GetCurrentDate()
secs_now = DateToSeconds(date_now)
date_new = SecondsToDate(secs_now + 30)
getLogger().warning("Next stop at: %s", date_new)
setNextShutdownDate(date_new)

# lance le poweroff du Raspberry et éteint le WittyPi
# en principe le doShutdown() lance le shutdown -h now,
# sauf s'il y a un fichier /boot/wittypi.lock
# Donc on ajoute un poweroff en plus...
getLogger().warning("doShutdown until: %s", nextStartDateValue)

if not is_raspberry_pi():
    getLogger().warning("Not a Raspberry Pi, so no poweroff")
    sys.exit(0)

doShutdown()
cmd = "sudo poweroff"
getLogger().warning(cmd)
result = run(cmd, capture_output=True, universal_newlines=True, shell=True, check=False)
sys.exit(0)
