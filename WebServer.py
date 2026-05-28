#!/usr/bin/env python3
"""Application Web pour configurer les scanners"""

import os
import sys
from subprocess import run, CalledProcessError
from time import sleep
import argparse
import shutil
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    send_from_directory,
)

from version import __version__
from Scanner import (
    ScannerData,
    ScannerPreview,
    updateScanParameters,
    listConfigScanner,
    initScanners,
    ResolutionList,
    ColorList,
)
from Hub import (
    ReadScannerConfigFromServer,
    SendScannerConfigToServer,
    GetWifiSSID,
    GetIP,
    getSSHPort,
    getScanorhizeServer,
    getTokens,
    HubData,
    ReadHubConfigFromServer,
    SendHubConfigToServer,
    get_hub_info,
)
from DateUtils import ValidateDate
from ConfigApp import (
    getLogger,
    getDisplayFile,
    getImageDir,
    is_debug,
    is_prod,
    ConfigApp,
    CONFIG_APP_FILE,
)
from Miscellaneous import (
    chaineIntwitherror,
    check_connectivity,
    InitGPIO,
    initDisplayFile,
)
from utils import sanitize_output
from WittyPy_utilities import (
    get_shutdown_time,
    get_startup_time,
    get_default_on,
    is_mc_connected,
    is_WittyPi_3,
    is_WittyPi_4,
    is_WittyPi_5,
    parse_wittypi_time
)
from OSUtils import is_raspberry_pi
from pin_config import get_pin_array

parser = argparse.ArgumentParser(
    prog="WebServer.py",
    usage="%(prog)s [--version]",
    epilog="""Lance l'application web de gestion des scanners""",
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
    print(f"WebServer.py version: {__version__}")
    sys.exit(0)

initDisplayFile()
getLogger().info("Start WebServer.py version: %s", __version__)
Hub = HubData()

try:
    # On lance le tunnel SSH inverse pour la maintenance à distance si on a de la connectivité internet
    # Lancer le tunnel SSH dans l'application Web permet de d'afficher le port SSH à utiliserdans l'application Web.
    # On ne fait que 3 tenttatives, car on a déjà essayé 25 fois dans ScanorhizeStart.py
    check_connectivity(3)
    cmd = f"ssh -fN -R {getSSHPort()}:localhost:22 pi@{getScanorhizeServer()} -E Log/ssh.log"
    run(cmd, shell=True, capture_output=True, text=True, check=False)
    getLogger().info(
        "Tunnel SSH inverse créé sur le port %d pour le serveur %s",
        getSSHPort(),
        getScanorhizeServer(),
    )
except RuntimeError as e:
    has_internet = False
    getLogger().error(
        "Error pas de connectivité internet: %s, on ne lance pas le tunnel SSH", e
    )

getLogger().info("Launch Web app")
app = Flask(__name__)


def get_common_template_vars():
    """Get common variables for templates with fresh hub_info"""
    return {
        "SSID": GetWifiSSID(),
        "IP": GetIP(),
        "hub_info": get_hub_info(),
        "SSH_PORT": getSSHPort(),
        "version": __version__,
    }


def get_hub_config_string():
    """Generate hub configuration string for display"""
    hub_info = get_hub_info()
    hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery: {hub_info[0]:.2f}V ({hub_info[1]}%)
USB Space: {hub_info[2]}MB ({hub_info[3]}%)
Temperature: {hub_info[4]:.1f}°C
Over Temperature Action: {Hub.over_temperature_action}
Over Temperature Point: {Hub.over_temperature_point}°C
Get Shutdown Time: {get_shutdown_time()}
Get Startup Time: {get_startup_time()}"""

    if is_debug():
        hub_config += f"\nToken: {Hub.token}"

    return hub_config


# On initialise le Hub
Hub.read_config()
Hub.write_config()


# This function does not allow caching of images from browser
@app.after_request
def add_header(response):
    # print("add_header", response)
    response.headers["Cache-Control"] = "public, max-age=0"
    return response


@app.route("/images/<path:filename>")
def serve_image(filename):
    """Sert les images d'acquisition depuis getImageDir()"""
    return send_from_directory(getImageDir(), filename)


@app.route("/", methods=["POST", "GET"])
def index():
    if request.method == "POST":
        cmd_pkill = "sudo pkill -f TakePictures.py"
        run(cmd_pkill, shell=True, capture_output=False, text=True, check=False)

    return render_template(
        "index.html",
        ScannerID="001",
        imagename1="1.jpg",
        imagename2="2.jpg",
        imagename3="3.jpg",
        **get_common_template_vars(),
    )


@app.route("/stream")
def stream():
    def generate():
        with open(getDisplayFile(), "r", encoding="utf-8") as f:
            while True:
                yield f.read()
                sleep(5)

    return app.response_class(generate(), mimetype="text/plain")


def parse_period(value):
    """Parse period value that can be in seconds (s) or days (d) format"""
    try:
        if value.endswith("d"):
            return int(float(value[:-1]) * 86400)  # Convert days to seconds
        if value.endswith("s"):
            return int(value[:-1])
        return int(value)  # Default to seconds if no unit specified
    except (ValueError, AttributeError):
        return 0


def format_period(seconds):
    """Format period in seconds to display in days if greater than 21600s (6 hours)"""
    if seconds is None or seconds == 0:
        return "3600s"  # Default to 1 hour
    if seconds >= 21600:  # Greater than or equal to 6 hours
        return f"{seconds/86400:.1f}d"
    return f"{seconds}s"


@app.route("/Scanner/<scan_num_str>", methods=["GET"])
def ScannerPage(scan_num_str: str):
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    i_scan = int(scan_num_str) - 1
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])

    # Get output message from query parameters if it exists and sanitize it
    output = sanitize_output(request.args.get("output", None))

    Scanner.ScannerName = f"Scanner-{i_scan + 1}"
    Scannerparam = updateScanParameters(Scanner)
    getLogger().info("Scanner n° : %s", str(i_scan + 1))
    # Scanner.printScanner()
    filename = str(i_scan + 1) + ".jpg"
    return render_template(
        "Scanner.html",
        **Scannerparam,
        scan_num_str=scan_num_str,
        imagename=filename,
        output=output,
        **get_common_template_vars(),
    )


def process_scanner_form_data(form, Scanner, listScannerconfigs, i_scan):
    """Process form data for Scanner configuration and update Scanner object.

    Args:
        form: The form data from the request
        Scanner: The ScannerData object to update
        listScannerconfigs: List of scanner configuration files
        i_scan: Index of the current scanner

    Returns:
        tuple: (success, error_message) where success is a boolean and error_message is a string
    """
    try:
        # Update Scanner object with form data
        try:
            resolution_index = int(form.get("resolution", "1"))
            if 1 <= resolution_index <= len(ResolutionList):
                Scanner.resolution = ResolutionList[resolution_index - 1]
            else:
                getLogger().warning(
                    "Invalid resolution index: %d, keeping current: %s",
                    resolution_index,
                    Scanner.resolution,
                )
        except (ValueError, TypeError) as e:
            getLogger().warning(
                "Error parsing resolution: %s, keeping current: %s",
                e,
                Scanner.resolution,
            )

        try:
            mode_index = int(form.get("mode", "1"))
            if 1 <= mode_index <= len(ColorList):
                Scanner.mode = ColorList[mode_index - 1]
            else:
                getLogger().warning(
                    "Invalid mode index: %d, keeping current: %s",
                    mode_index,
                    Scanner.mode,
                )
        except (ValueError, TypeError) as e:
            getLogger().warning(
                "Error parsing mode: %s, keeping current: %s", e, Scanner.mode
            )

        # Update numeric fields with validation, using empty string as default
        Scanner.l = chaineIntwitherror(form.get("l", ""), Scanner.l, 0, Scanner.x_max)
        Scanner.t = chaineIntwitherror(form.get("t", ""), Scanner.t, 0, Scanner.y_max)
        Scanner.x = chaineIntwitherror(form.get("x", ""), Scanner.x, 0, Scanner.x_max)
        Scanner.y = chaineIntwitherror(form.get("y", ""), Scanner.y, 0, Scanner.y_max)
        Scanner.quality = chaineIntwitherror(
            form.get("quality", ""), Scanner.quality, 0, 90
        )

        # Update other fields
        if "token" in form and form["token"] != "":
            Scanner.token = form["token"]
        Scanner.UseServer = chaineIntwitherror(
            form.get("UseServer", "0"), Scanner.UseServer, 0, 1
        )
        Scanner.TimeBeforeScan = chaineIntwitherror(
            form.get("TimeBeforeScan", "0"), Scanner.TimeBeforeScan, 0, 60
        )
        Scanner.TimeAfterScan = chaineIntwitherror(
            form.get("TimeAfterScan", "0"), Scanner.TimeAfterScan, 0, 60
        )
        Scanner.enable = 1 if "enable" in form else 0

        # Save the updated Scanner object
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])
        getLogger().warning("Updated Scanner object: %s", Scanner.__dict__)

        return True, "Configuration saved successfully"

    except Exception as e:
        getLogger().error("Error processing form data: %s", str(e))
        return False, f"Error saving configuration: {str(e)}"


@app.route("/Scanner/<actionName>/<scan_num_str>", methods=["GET", "POST"])
def action(actionName: str, scan_num_str: str):
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    i_scan = int(scan_num_str) - 1
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])
    Scanner.ScannerName = f"Scanner-{i_scan + 1}"
    getLogger().info("Scanner n° : %s", str(i_scan + 1))
    # Scanner.printScanner()

    if actionName == "acqimg":
        InitGPIO()
        result = ScannerPreview(Scanner, i_scan)
        Scanner.LastImgFile = result[0]
        Scanner.error = result[1]
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])
        return redirect(
            url_for(
                "ScannerPage", scan_num_str=scan_num_str, output="Image scan completed"
            )
        )

    if actionName == "GetConfig":
        result = ReadScannerConfigFromServer(Scanner)
        if result == 0:
            output_message = f"Configuration successfully downloaded from server for {Scanner.ScannerName}"
        else:
            output_message = (
                f"Error downloading configuration from server for {Scanner.ScannerName}"
            )
        return redirect(
            url_for(
                "ScannerPage",
                scan_num_str=scan_num_str,
                output=sanitize_output(output_message),
            )
        )

    if actionName == "SendConfig":
        if request.method == "POST":
            # Process form data and save locally
            success, message = process_scanner_form_data(
                request.form, Scanner, listScannerconfigs, i_scan
            )
            if not success:
                return redirect(
                    url_for(
                        "ScannerPage",
                        scan_num_str=scan_num_str,
                        output=sanitize_output(message),
                    )
                )

            # Then send to server
            result = SendScannerConfigToServer(Scanner)
            if result == 0:
                output_message = "Configuration sent to server successfully"
            else:
                output_message = f"Error sending configuration to server: {result}"

            return redirect(
                url_for(
                    "ScannerPage",
                    scan_num_str=scan_num_str,
                    output=sanitize_output(output_message),
                )
            )

    if actionName == "WriteConfig":
        if request.method == "POST":
            success, message = process_scanner_form_data(
                request.form, Scanner, listScannerconfigs, i_scan
            )
            return redirect(
                url_for(
                    "ScannerPage",
                    scan_num_str=scan_num_str,
                    output=sanitize_output(message),
                )
            )

    return redirect(url_for("ScannerPage", scan_num_str=scan_num_str))


@app.route("/Hub", methods=["POST", "GET"])
def HubPage():
    Hub.read_config()

    # Format Hub configuration for display with all values
    hub_config = get_hub_config_string()

    # Get the pin array configuration
    pin_array = get_pin_array()

    # Get output message from query parameters if it exists and sanitize it
    output = sanitize_output(request.args.get("output", None))

    return render_template(
        "Hub.html",
        hub_config=hub_config,
        pin_array=pin_array,
        use_server=Hub.use_server,
        connect_timeout=Hub.connect_timeout,
        max_time=Hub.max_time,
        delta_time=Hub.delta_time,
        offline=Hub.offline,
        sync_images=Hub.sync_images,
        send_thumbnails_only=Hub.send_thumbnails_only,
        todo=Hub.todo,
        acquisition_schedule=Hub.acquisition_schedule,
        output=output,
        **get_common_template_vars(),
    )


@app.route("/update_version", methods=["POST", "GET"])
def update_version():

    if not is_raspberry_pi():
        return redirect(
            url_for("HubPage", output=sanitize_output("No update, not on Raspberry Pi"))
        )

    try:
        cmd_update = "s3cmd --no-preserve sync --delete-removed --exclude-from Scanorhize/s3exclude.txt s3://hubs/hub-master/home/pi/Scanorhize/ /home/pi/Scanorhize/"
        getLogger().info("Update version: %s", cmd_update)
        result = run(
            cmd_update,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )

        return redirect(
            url_for(
                "HubPage", output=sanitize_output(f"Update version OK: {result.stdout}")
            )
        )

    except CalledProcessError as e:
        return redirect(
            url_for("HubPage", output=sanitize_output(f"Command failed: {e.stderr}"))
        )


@app.route("/App", methods=["GET"])
def AppPage():
    # Get ConfigApp instance
    config = ConfigApp()

    # Create dictionary with all relevant attributes
    app_config = {
        "environment": config.environment,  # Always use the environment variable
        "config_app_file": config.config_app_file,
        "log_level": config.log_level,
        "config_dir": config.config_dir,
        "config_hub_file": config.config_hub_file,
        "display_file": config.display_file,
        "battery_file": config.battery_file,
        "usb_dir": config.usb_dir,
        "image_dir": config.image_dir,
        "s3_bucket": config.s3_bucket,
        "scanorhize_server": config.scanorhize_server,
        "th_x": config.th_x,
        "th_y": config.th_y,
    }

    return render_template(
        "App.html", app_config=app_config, **get_common_template_vars()
    )


@app.route("/Tests", methods=["GET"])
def TestsPage():
    return render_template("Tests.html", **get_common_template_vars())


@app.route("/tests/run/<test_name>", methods=["GET"])
def run_test(test_name: str):
    try:
        if test_name == "internet":
            try:
                check_connectivity(1)
                return jsonify(ok=True, message="Internet connection is available.")
            except RuntimeError as e:
                return jsonify(ok=False, message=str(e))

        if test_name == "s3":
            config = ConfigApp()
            result = run(
                f"s3cmd ls {config.s3_bucket}",
                shell=True, capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                return jsonify(ok=True, message=f"S3 bucket {config.s3_bucket} is accessible using `s3cmd`.", next_test="s3-test")
                
            return jsonify(ok=False, message=result.stderr or "Could not reach {config.s3_bucket} bucket.")
            
        if test_name == "s3-test":
            config = ConfigApp()
            result = run(
                f"s3cmd ls s3://humeos-test",
                shell=True, capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                return jsonify(ok=True, message=f"S3 bucket s3://humeos-test is accessible using `s3cmd`.")
                
            return jsonify(ok=False, message=result.stderr or "Could not reach s3://humeos-test bucket.")

        if test_name == "ssh":
            result = run(
                "pgrep -a ssh", shell=True, capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                return jsonify(ok=True, message=f"Active SSH processes:\n{result.stdout}")
            return jsonify(ok=False, message="No active SSH tunnel found.")

        if test_name == "take-pictures":
            result = run(
                "python3 TakePictures.py -f",
                shell=True, capture_output=True, text=True, check=False,
            )
            stdout = {line.split(":")[0]: line.split(":", 1)[1]
                      for line in result.stdout.splitlines() if ":" in line}
            pictures_taken = int(stdout.get("PICTURES_TAKEN", 0))
            scanners = stdout.get("SCANNERS", "")
            
            if scanners:
                scanner_list = scanners.replace(",", ", ")
                total = len(scanners.split(",")) if scanners else 0

                if result.returncode == 0:
                    return jsonify(ok=True, message=f"{pictures_taken}/{total} picture(s) taken — scanners: {scanner_list}", next_test="wait-for-pictures-upload")
                    
            else:
                return jsonify(ok=False, message=f"No scanner found")
                
            return jsonify(ok=False, message=f"{pictures_taken}/{total} picture(s) taken — scanners: {scanner_list}\n{result.stderr or ''}")


        if test_name == "wittypi":
            if not is_mc_connected():
                return jsonify(ok=False, message="WittyPi not detected on I2C bus.")

            if is_WittyPi_5():
                model = "WittyPi 5"
            elif is_WittyPi_4():
                model = "WittyPi 4"
            elif is_WittyPi_3():
                model = "WittyPi 3"
            else:
                model = "WittyPi (unknown version)"

            startup = parse_wittypi_time(get_startup_time())
            shutdown = parse_wittypi_time(get_shutdown_time())

            # startup/shutdown expected as datetime objects
            from datetime import datetime
            now = datetime.now()

            if startup:
                startup_left = startup - now
                startup_left_str = str(startup_left).split('.')[0]
            else:
                startup_left_str = "N/A"

            if shutdown:
                shutdown_left = shutdown - now
                shutdown_left_str = str(shutdown_left).split('.')[0]
            else:
                shutdown_left_str = "N/A"

            default_on = get_default_on()  # 0=immediately on, 255=stay off

            if default_on == 255:
                default_on = "<b style='font-weight:bold; color:orange;'>⚠ OFF</b>"
            elif default_on == 0:
                default_on = "Immediately turn ON"
            else:
                default_on = f"Turn ON after {default_on}s"
                
            warning_text = ""
            
            try:
                if startup and shutdown and startup < shutdown:
                    warning_text = "\n  → <b style='font-weight:bold; color:orange;'>⚠ WARNING</b>:        Next wakeup occurs BEFORE next shutdown."
            except Exception:
                warning_text = ""
                pass
                
                
            return jsonify(
                ok=True,
                message=(
                    f"\n"
                    f"  → Model:            {model}\n"
                    f"  → Default on power: {default_on}\n"
                    f"  → Next <span style='color:red'>shutdown</span>:    {shutdown} ({shutdown_left_str} left)\n"
                    f"  → Next <span style='color:green'>wakeup</span>:      {startup} ({startup_left_str} left)"
                    f"{warning_text}"
                ),
            )


        if test_name == "scanners-config-files":
            configs = listConfigScanner()
            if not configs:
                return jsonify(ok=False, message="No scanner config files found.")
            lines = []
            configuredScanners = 0
            for cfg in configs:
                scanner = ScannerData()
                scanner.ReadScannerConfig(cfg)
                if not scanner.device or scanner.device == "NoScannerDetected":
                    device_str = "<span style='font-weight:bold; color:orange;'>⚠</span> device missing or not detected"
                else:
                    device_str = scanner.device
                    configuredScanners += 1
                lines.append(f"  {cfg}: projectId={scanner.projectId}, sampleId={scanner.sampleId}, device={device_str}")
                
            if configuredScanners == 0:
                return jsonify(ok=False, message="Scanner configs found:\n" + "\n".join(lines) + "\n  → No scanner configured", summary=f"{len(lines)} scanner config file(s) found")
            else:
                return jsonify(ok=True, message="Scanner configs found:\n" + "\n".join(lines) + f"\n  → {configuredScanners} scanner(s) configured", summary=f"{len(lines)} scanner config file(s) found")
            
        if test_name == "upload-pictures-service":
            try:
                result = run(
                    ["systemctl", "is-active", "upload-pictures"],
                    capture_output=True,
                    text=True
                )

                if result.stdout.strip() == "active":
                    return jsonify(ok=True, message="Upload Pictures service is active.", next_test="copy-test-picture")
                    
                else:
                    return jsonify(ok=False, message=f"Upload Pictures service status: {result.stdout.strip()}")

            except Exception as e:
                return jsonify(ok=False, message="Upload Pictures service status is not 'active'")
                
        if test_name == "copy-test-picture":
            configs = listConfigScanner()
            if not configs:
                return jsonify(ok=False, message="No scanner config files found.")
            for cfg in configs:
                scanner = ScannerData()
                scanner.ReadScannerConfig(cfg)
                if scanner.projectId and scanner.sampleId:
                    from datetime import datetime
                    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    testFile = "/home/pi/Scanorhize/static/1.jpg"
                    destFile = f"/media/pi/Image/{scanner.projectId}/{scanner.sampleId}/test_{now}.jpg"
                    source = Path(testFile)
                    destination = Path(destFile)

                    try:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(source, destination)
                        now = datetime.now().strftime("%-m/%-d/%Y, %-I:%M:%S %p")
                        return jsonify(ok=True, message=f"Test file {testFile} copied to {destFile}\n[{now}] <b style='color:orange;'>⌛ IN PROGRESS</b>: Test picture is waiting to be uploaded to server", next_test="wait-for-pictures-upload")

                    except FileNotFoundError:
                        return jsonify(ok=False, message=f"Test file {testFile} not found.")
                        
                    except Exception as e:
                        return jsonify(ok=False, message=str(e))
                        
                    break
            
            return jsonify(ok=False, message="No scanner config files found.")
            
        if test_name == "wait-for-pictures-upload":
            configs = listConfigScanner()
            if not configs:
                return jsonify(ok=False, message="No scanner config files found.")
            for cfg in configs:
                scanner = ScannerData()
                scanner.ReadScannerConfig(cfg)
                if scanner.projectId and scanner.sampleId:
                    from datetime import datetime
                    destFile = f"/media/pi/Image/{scanner.projectId}/{scanner.sampleId}"
                    destination = Path(destFile)
                    
                    file_count = sum(1 for f in destination.iterdir() if f.is_file())

                    if file_count == 0:
                        return jsonify(ok=True, message=f"Test picture uploaded to server (no more pictures in folder)")
                    else:
                        sleep(3)
                        return jsonify(processing=True, message=f"Uploading {file_count} picture(s) to server", next_test="wait-for-pictures-upload")

        if test_name == "speed":
            import time
            from datetime import datetime
            local_path = "/tmp/2MB.jpg"
            s3_path = "s3://humeos-test/tests/2MB.jpg"

            try:
                # -------------------
                # DOWNLOAD
                # -------------------
                t0 = time.time()

                run(
                    ["s3cmd", "--force", "get", s3_path, local_path],
                    check=True
                )

                t1 = time.time()

                download_time = t1 - t0
                size_bytes = os.path.getsize(local_path)
                download_speed = (size_bytes / (1024 * 1024)) / download_time

                # -------------------
                # UPLOAD
                # -------------------
                t2 = time.time()

                run(
                    ["s3cmd", "put", local_path, s3_path],
                    check=True
                )

                t3 = time.time()

                upload_time = t3 - t2
                upload_speed = (size_bytes / (1024 * 1024)) / upload_time

                return jsonify(
                    ok=True,
                    message=(
                        f"Download: {download_time:.2f}s ({download_speed:.2f} MB/s) | "
                        f"Upload: {upload_time:.2f}s ({upload_speed:.2f} MB/s)"
                    ),
                    summary=(
                        f"Download: {download_time:.2f}s ({download_speed:.2f} MB/s) | "
                        f"Upload: {upload_time:.2f}s ({upload_speed:.2f} MB/s)"
                    )
                )

            except Exception as e:
                return jsonify(ok=False, message=str(e))
                       
        
        return jsonify(ok=False, message=f"Unknown test: {test_name}")

    except Exception as e:
        return jsonify(ok=False, message=str(e))


@app.route("/get-app-config", methods=["GET"])
def get_app_config():
    try:
        # Get the requested environment from query parameters
        requested_env = request.args.get("environment", "PROD")

        # Create a temporary ConfigApp instance with the requested environment
        temp_config = ConfigApp()
        temp_config.environment = requested_env
        temp_config.config_app_file = f"{CONFIG_APP_FILE}-{requested_env.lower()}.json"

        # Load the configuration for the requested environment
        temp_config.load_config()

        # Create dictionary with all relevant attributes
        app_config = {
            "environment": temp_config.environment,
            "config_app_file": temp_config.config_app_file,
            "log_level": temp_config.log_level,
            "config_dir": temp_config.config_dir,
            "config_hub_file": temp_config.config_hub_file,
            "display_file": temp_config.display_file,
            "battery_file": temp_config.battery_file,
            "usb_dir": temp_config.usb_dir,
            "image_dir": temp_config.image_dir,
            "s3_bucket": temp_config.s3_bucket,
            "scanorhize_server": temp_config.scanorhize_server,
        }

        return jsonify(app_config)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/update-app-config", methods=["POST"])
def update_app_config():
    try:
        # Get the new values from the form
        new_log_level = request.form.get("log_level")
        new_usb_dir = request.form.get("usb_dir")
        new_th_x = request.form.get("th_x")
        new_th_y = request.form.get("th_y")

        if new_log_level not in ["WARNING", "INFO", "DEBUG"]:
            return render_template(
                "App.html",
                app_config=ConfigApp().__dict__,
                output=sanitize_output(
                    "Invalid log level value. Must be WARNING, INFO, or DEBUG."
                ),
                **get_common_template_vars(),
            )

        # Validate thumbnail dimensions
        try:
            th_x_val = int(new_th_x)
            th_y_val = int(new_th_y)
            if th_x_val <= 0 or th_y_val <= 0:
                raise ValueError("Thumbnail dimensions must be positive integers")
        except (ValueError, TypeError):
            return render_template(
                "App.html",
                app_config=ConfigApp().__dict__,
                output=sanitize_output(
                    "Invalid thumbnail dimensions. Must be positive integers."
                ),
                **get_common_template_vars(),
            )

        # Get ConfigApp instance
        config = ConfigApp()
        config.log_level = new_log_level
        config.usb_dir = new_usb_dir
        config.th_x = th_x_val
        config.th_y = th_y_val

        # Save the configuration
        if config.save_config() == 0:
            # Reload the configuration to get the correct attributes
            config.load_config()
            output = (
                f"Configuration updated successfully. Log level set to {new_log_level}"
            )
        else:
            output = "Error saving configuration"

        # Recreate app_config with updated values
        app_config = {
            "environment": config.environment,
            "config_app_file": config.config_app_file,
            "log_level": config.log_level,
            "config_dir": config.config_dir,
            "config_hub_file": config.config_hub_file,
            "display_file": config.display_file,
            "battery_file": config.battery_file,
            "usb_dir": config.usb_dir,
            "image_dir": config.image_dir,
            "s3_bucket": config.s3_bucket,
            "scanorhize_server": config.scanorhize_server,
            "th_x": config.th_x,
            "th_y": config.th_y,
        }

        return render_template(
            "App.html",
            app_config=app_config,
            output=sanitize_output(output),
            **get_common_template_vars(),
        )

    except Exception as e:
        return render_template(
            "App.html",
            app_config=ConfigApp().__dict__,
            output=sanitize_output(f"Error updating configuration: {str(e)}"),
            **get_common_template_vars(),
        )


def validate_crontab_syntax(schedule: str) -> bool:
    """Valide la syntaxe d'une expression crontab

    Args:
        schedule: Expression crontab à valider

    Returns:
        bool: True si valide, False sinon
    """
    try:
        from croniter import croniter
        from datetime import datetime

        # Tester si croniter peut parser l'expression
        croniter(schedule, datetime.now())
        return True
    except (ValueError, KeyError):
        return False


def process_hub_form_data(form):
    """Process form data for Hub configuration and update Hub object.

    Args:
        form: The form data from the request

    Returns:
        tuple: (success, error_message) where success is a boolean and error_message is a string
    """
    try:
        # Update Hub object with form data
        Hub.use_server = "use_server" in form
        # Parse numeric values with validation
        Hub.connect_timeout = int(form.get("connect_timeout", 10))
        Hub.max_time = int(form.get("max_time", 300))
        Hub.delta_time = int(form.get("delta_time", 300))
        # Handle checkboxes
        Hub.offline = "offline" in form
        Hub.sync_images = "sync_images" in form
        Hub.send_thumbnails_only = "send_thumbnails_only" in form
        Hub.todo = "todo" in form

        # Valider et sauvegarder le schedule crontab
        new_schedule = form.get("acquisition_schedule", "0 8 * * *")
        old_schedule = Hub.acquisition_schedule

        # Validation basique de la syntaxe crontab
        schedule_changed = False
        if validate_crontab_syntax(new_schedule):
            if new_schedule != old_schedule:
                Hub.acquisition_schedule = new_schedule
                schedule_changed = True
                getLogger().info(
                    "Acquisition schedule updated: %s -> %s", old_schedule, new_schedule
                )
        else:
            getLogger().warning(
                "Invalid crontab syntax: %s, keeping current", new_schedule
            )

        # Save the Hub configuration locally
        Hub.write_config()

        # Si le schedule a changé, recalculer et mettre à jour le réveil WittyPi
        if schedule_changed:
            try:
                from Hub import calculate_next_wakeup_from_crontab

                next_wakeup = calculate_next_wakeup_from_crontab()
                getLogger().info(
                    "WittyPi wakeup updated after schedule change: %s", next_wakeup
                )
            except Exception as e:
                getLogger().error(
                    "Error updating WittyPi wakeup after schedule change: %s", e
                )

        return True, "Configuration saved successfully"
    except Exception as e:
        return False, f"Error processing form data: {str(e)}"


@app.route("/write_config", methods=["GET", "POST"])
def write_config():
    if request.method == "POST":
        success, message = process_hub_form_data(request.form)
        return redirect(
            url_for(
                "HubPage",
                output=sanitize_output(
                    f"{'Success: ' if success else 'Error: '}{message}"
                ),
            )
        )
    return redirect(url_for("HubPage"))


@app.route("/send-hub-config", methods=["POST"])
def send_hub_config():
    try:
        # First process the form data and save locally
        success, message = process_hub_form_data(request.form)
        if not success:
            return redirect(url_for("HubPage", output=sanitize_output(message)))

        # Then send to server
        result = SendHubConfigToServer()
        if result == 0:
            return redirect(
                url_for(
                    "HubPage",
                    output=sanitize_output("Configuration successfully sent to server"),
                )
            )

        return redirect(
            url_for(
                "HubPage",
                output=sanitize_output("Error sending configuration to server"),
            )
        )

    except Exception as e:
        return redirect(
            url_for(
                "HubPage",
                output=sanitize_output(
                    f"Error sending configuration to server: {str(e)}"
                ),
            )
        )


@app.route("/get-hub-config", methods=["GET"])
def get_hub_config():
    try:
        result = ReadHubConfigFromServer()

        # Reload the Hub configuration after downloading from server
        Hub.read_config()

        if result == 0:
            # Redirect to /Hub with success message
            return redirect(
                url_for(
                    "HubPage",
                    output=sanitize_output(
                        "Configuration successfully downloaded from server"
                    ),
                )
            )

        # Redirect to /Hub with error message
        return redirect(
            url_for(
                "HubPage",
                output=sanitize_output("Error downloading configuration from server"),
            )
        )

    except Exception as e:
        # Redirect to /Hub with error message
        return redirect(
            url_for(
                "HubPage",
                output=sanitize_output(
                    f"Error downloading configuration from server: {str(e)}"
                ),
            )
        )


@app.route("/init_hub", methods=["GET", "POST"])
def init_hub():
    try:
        Hub.read_config()
        # Permet de mettre à jour les valeurs de Hub.macAddress et Hub.model
        # dans les 2 cas suivants:
        # 1. Le fichier Hub.json n'existe pas
        # 2. Le fichier Hub.json provient d'un autre Hub
        Hub.write_config()

        getLogger().info("Start InitScanners")
        # Run initScanners() to initialize scanners
        # Init Scanners before getting tokens, because this operation
        # can be completed without network
        initScanners()
        getLogger().info("End InitScanners")
        Scanner = ScannerData()
        for CurrentScanner in listConfigScanner():
            Scanner.ReadScannerConfig(CurrentScanner)
            SendScannerConfigToServer(Scanner)
        # Run getTokens() to get authentication tokens
        getLogger().info("Start init-hub")
        tokens_result = getTokens()
        if tokens_result != 0:
            return redirect(
                url_for("HubPage", output=sanitize_output("Failed to get tokens"))
            )

        getLogger().info("End init-hub")
        return redirect(
            url_for("HubPage", output=sanitize_output("Hub initialized successfully"))
        )

    except (OSError, ValueError) as e:
        return redirect(url_for("HubPage", output=sanitize_output(f"Error: {str(e)}")))


@app.route("/scan_acq", methods=["GET", "POST"])
def scan_acq():
    getLogger().info("Force scanners acquisition")
    try:
        cmd_acq = "python3 TakePictures.py -f"
        getLogger().info("Scan Acq: %s", cmd_acq)
        result = run(cmd_acq, shell=True, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            getLogger().info("Scan Acq: OK")
            return redirect(
                url_for("HubPage", output=sanitize_output("Scanners acquisition OK"))
            )

        getLogger().warning(
            "Scan Acq: failed (return code: %d, stderr: %s)",
            result.returncode,
            result.stderr,
        )
        return redirect(
            url_for("HubPage", output=sanitize_output("Scanners acquisition failed"))
        )

    except CalledProcessError as e:
        return redirect(
            url_for("HubPage", output=sanitize_output(f"Command failed: {e.stderr}"))
        )


@app.route("/poweroff", methods=["POST"])
def stop_server():

    if not is_raspberry_pi():
        return render_template(
            "Hub.html",
            output=sanitize_output("Not on Raspberry Pi"),
            **get_common_template_vars(),
        )

    # Before remove the USB key, we need to stop the server
    cmdeject = "sudo eject /dev/sda"
    result = run(
        cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    getLogger().info("Eject command: %s", cmdeject)
    if result.returncode == 0:
        getLogger().info("SD card ejected successfully")
    else:
        getLogger().warning(
            "SD card eject failed (return code: %d, stderr: %s)",
            result.returncode,
            result.stderr,
        )

    # Reset the verbosity level int the ConfigApp file
    # otherwise, the Raspberry Pi will not poweroff
    # if the log level stays to DEBUG
    config = ConfigApp()
    config.log_level = "WARNING"
    config.save_config()
    # On enlève également tout fichier DEBUG
    try:
        os.remove("DEBUG")
        getLogger().info("remove_image_files: removed DEBUG")
    except (FileNotFoundError, PermissionError) as e:
        getLogger().warning("Error removing file DEBUG: %s", e)

    run(
        "sudo poweroff",
        capture_output=True,
        universal_newlines=True,
        shell=True,
        check=False,
    )
    return "OK"


if __name__ == "__main__":
    if is_prod():
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
    else:
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
