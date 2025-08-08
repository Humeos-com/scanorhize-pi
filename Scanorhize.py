"""Application Web pour configurer les scanners"""

import os
import sys
from subprocess import run, CalledProcessError
from time import sleep
import random  # Add this import
import argparse
from flask import Flask, render_template, request, jsonify, redirect, url_for

from version import __version__
from Scanner import (
    ScannerData,
    ScannerPreview,
    updateScanParameters,
    listConfigScanner,
    initScanners,
    ResolutionList,
    ColorList,
    calculate_and_set_next_date,
)
from Hub import (
    ReadScannerConfigFromServer,
    SendScannerConfigToServer,
    GetWifiSSID,
    GetIP,
    updateServer,
    HubData,
    getTokens,
    ReadHubConfigFromServer,
    SendHubConfigToServer,
    get_hub_info,
)
from ConfigApp import (
    getLogger,
    getDisplayFile,
    getScanorhizeServer,
    is_debug,
    is_prod,
    ConfigApp,
    CONFIG_APP_FILE,
)
from Miscellaneous import (
    chaineIntwitherror,
    InitGPIO,
    initDisplayFile,
    check_connectivity,
    sync_time,
)
from OSUtils import is_raspberry_pi
from pin_config import get_pin_array

parser = argparse.ArgumentParser(
    prog="Scanorhize.py",
    usage="%(prog)s [--version]",
    epilog="""Lance l'application web de gestion des scanners""",
)
parser.add_argument(
    "-v", "--version",
    action="store_true",
    help="Affiche la version du programme",
)
args = parser.parse_args()
if args.version:
    print(f"Scanorhize.py version: {__version__}")
    sys.exit(0)

initDisplayFile()
getLogger().warning("Start Scanorhize.py version: %s", __version__)
Hub = HubData()
getLogger().warning("Launch Web app")
app = Flask(__name__)

has_internet = False
SSH_PORT = random.randint(2223, 2299)  # Random port between 2223-2299

def get_common_template_vars():
    """Get common variables for templates with fresh hub_info"""
    return dict(
        SSID=GetWifiSSID(),
        IP=GetIP(),
        hub_info=get_hub_info(),
        SSH_PORT=SSH_PORT,
        version=__version__
    )

try:
    check_connectivity()
    has_internet = True
    getLogger().warning("Internet OK !")
    sync_time()
    # On crée un tunnel SSH inverse pour la maintenance à distance
    cmd = f"ssh -fN -R {SSH_PORT}:localhost:22 debian@{getScanorhizeServer()}  -p 2222 -E Log/ssh.log"
    run(cmd, shell=True, capture_output=True, text=True, check=False)
    getLogger().warning("Tunnel SSH inverse créé sur le port %d pour le serveur %s", SSH_PORT, getScanorhizeServer())

except RuntimeError as exc:
    getLogger().error("No internet connection: %s", exc)

# A priori, même sans connectivité, on doit avoir le SSID Scanorhize et une IP
getLogger().warning("SSID: %s", GetWifiSSID())
getLogger().warning("IP: %s", GetIP())


# This function does not allow caching of images from browser
@app.after_request
def add_header(response):
    # print("add_header", response)
    response.headers["Cache-Control"] = "public, max-age=0"
    return response


@app.route("/", methods=["POST", "GET"])
def index():
    if request.method == "POST":
        cmd = "sudo pkill -f ScanorhizeProcess.py"
        run(cmd, shell=True, capture_output=True, text=True, check=False)

    return render_template(
        "index.html",
        ScannerID="001",
        imagename1="1.jpg",
        imagename2="2.jpg",
        imagename3="3.jpg",
        **get_common_template_vars()
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

    # Get output message from query parameters if it exists
    output = request.args.get("output", None)

    Scanner.ScannerName = f"Scanner-{i_scan + 1}"
    Scannerparam = updateScanParameters(Scanner)
    Scannerparam["PeriodeS"] = format_period(Scanner.PeriodeS)
    getLogger().warning("Scanner n° : %s", str(i_scan + 1))
    # Scanner.printScanner()
    filename = str(i_scan + 1) + ".jpg"
    return render_template(
        "Scanner.html",
        **Scannerparam,
        scan_num_str=scan_num_str,
        imagename=filename,
        output=output,
        **get_common_template_vars()
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
        Scanner.resolution = (
            ResolutionList[int(form["resolution"]) - 1]
            if int(form["resolution"]) <= 3
            else ResolutionList[0]
        )
        Scanner.mode = (
            ColorList[int(form["mode"]) - 1]
            if form["mode"] != Scanner.mode
            else Scanner.mode
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
        if form.get("StartDate", "") != "":
            Scanner.StartDate = form["StartDate"]
        Scanner.PeriodeS = parse_period(form.get("PeriodeS", "3600s"))
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

        # Recalculate next start date
        nextStartDateValue = calculate_and_set_next_date()
        getLogger().warning("Recalculated next start date: %s", nextStartDateValue)

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
    getLogger().warning("Scanner n° : %s", str(i_scan + 1))
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

    elif actionName == "GetConfig":
        result = ReadScannerConfigFromServer(Scanner)
        if result == 0:
            output_message = f"Configuration successfully downloaded from server for {Scanner.ScannerName}"
        else:
            output_message = (
                f"Error downloading configuration from server for {Scanner.ScannerName}"
            )
        return redirect(
            url_for("ScannerPage", scan_num_str=scan_num_str, output=output_message)
        )

    elif actionName == "SendConfig":
        if request.method == "POST":
            # Process form data and save locally
            success, message = process_scanner_form_data(
                request.form, Scanner, listScannerconfigs, i_scan
            )
            if not success:
                return redirect(
                    url_for("ScannerPage", scan_num_str=scan_num_str, output=message)
                )

            # Then send to server
            result = SendScannerConfigToServer(Scanner)
            if result == 0:
                output_message = "Configuration sent to server successfully"
            else:
                output_message = f"Error sending configuration to server: {result}"

            return redirect(
                url_for("ScannerPage", scan_num_str=scan_num_str, output=output_message)
            )

    elif actionName == "WriteConfig":
        if request.method == "POST":
            success, message = process_scanner_form_data(
                request.form, Scanner, listScannerconfigs, i_scan
            )
            return redirect(
                url_for("ScannerPage", scan_num_str=scan_num_str, output=message)
            )

    return redirect(url_for("ScannerPage", scan_num_str=scan_num_str))


@app.route("/Hub", methods=["POST", "GET"])
def HubPage():
    Hub.read_config()
    hub_info = get_hub_info()

    # Format Hub configuration for display with all values
    hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery: {hub_info[0]:.2f}V ({hub_info[1]}%)
USB Space: {hub_info[2]}MB ({hub_info[3]}%)
Temperature: {hub_info[4]:.1f}°C
Ping: {Hub.ping}"""

    if is_debug():
        hub_config += f"\nToken: {Hub.token}"

    # Get the pin array configuration
    pin_array = get_pin_array()

    # Get output message from query parameters if it exists
    output = request.args.get("output", None)

    return render_template(
        "Hub.html",
        **updateServer(Hub),
        hub_config=hub_config,
        pin_array=pin_array,
        use_server=Hub.use_server,
        connect_timeout=Hub.connect_timeout,
        max_time=Hub.max_time,
        delta_time=Hub.delta_time,
        offline=Hub.offline,
        sync_images=Hub.sync_images,
        todo=Hub.todo,
        output=output,
        **get_common_template_vars()
    )


@app.route("/update_version", methods=["POST", "GET"])
def update_version():
    hub_info = get_hub_info()
    hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery: {hub_info[0]:.2f}V ({hub_info[1]}%)
USB Space: {hub_info[2]}MB ({hub_info[3]}%)
Temperature: {hub_info[4]:.1f}°C
Ping: {Hub.ping}"""

    if is_debug():
        hub_config += f"\nToken: {Hub.token}"

    if not is_raspberry_pi():
        return render_template(
            "Hub.html",
            **updateServer(Hub),
            hub_config=hub_config,
            use_server=Hub.use_server,
            connect_timeout=Hub.connect_timeout,
            max_time=Hub.max_time,
            delta_time=Hub.delta_time,
            offline=Hub.offline,
            sync_images=Hub.sync_images,
            todo=Hub.todo,
            output="No update, not on Raspberry Pi",
            **get_common_template_vars()
        )
    try:
        cmd_update = "s3cmd --no-preserve sync s3://hubs/hub-master/home/pi/Scanorhize/ /home/pi/Scanorhize/"
        getLogger().warning("Update version: %s", cmd_update)
        result = run(
            cmd_update,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        return render_template(
            "Hub.html",
            **updateServer(Hub),
            hub_config=hub_config,
            use_server=Hub.use_server,
            connect_timeout=Hub.connect_timeout,
            max_time=Hub.max_time,
            delta_time=Hub.delta_time,
            offline=Hub.offline,
            sync_images=Hub.sync_images,
            todo=Hub.todo,
            output=result.stdout,
            **get_common_template_vars()
        )
    except CalledProcessError as e:
        return render_template(
            "Hub.html",
            **updateServer(Hub),
            hub_config=hub_config,
            use_server=Hub.use_server,
            connect_timeout=Hub.connect_timeout,
            max_time=Hub.max_time,
            delta_time=Hub.delta_time,
            offline=Hub.offline,
            sync_images=Hub.sync_images,
            todo=Hub.todo,
            output=f"Command failed: {e.stderr}",
            **get_common_template_vars()
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
    }

    return render_template(
        "App.html",
        app_config=app_config,
        **get_common_template_vars()
    )


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

        # Get hub info with error handling
        try:
            hub_info = get_hub_info()
        except Exception as e:
            getLogger().error("Error getting hub info: %s", str(e))
            hub_info = [0, 0, 0, 0, 0]  # Default values if get_hub_info fails

        if new_log_level not in ["WARNING", "INFO", "DEBUG"]:
            return render_template(
                "App.html",
                app_config=ConfigApp().__dict__,
                output="Invalid log level value. Must be WARNING, INFO, or DEBUG.",
                **get_common_template_vars()
            )

        # Get ConfigApp instance
        config = ConfigApp()
        config.log_level = new_log_level
        config.usb_dir = new_usb_dir

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
        }

        return render_template(
            "App.html",
            app_config=app_config,
            output=output,
            **get_common_template_vars()
        )

    except Exception as e:
        # Get hub info with error handling for error case too
        try:
            hub_info = get_hub_info()
        except Exception as e2:
            getLogger().error("Error getting hub info: %s", str(e2))
            hub_info = [0, 0, 0, 0, 0]  # Default values if get_hub_info fails

        return render_template(
            "App.html",
            app_config=ConfigApp().__dict__,
            output=f"Error updating configuration: {str(e)}",
            **get_common_template_vars()
        )


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
        Hub.todo = "todo" in form

        # Save the Hub configuration locally
        Hub.write_config()
        return True, "Configuration saved successfully"
    except Exception as e:
        return False, f"Error processing form data: {str(e)}"


@app.route("/write_config", methods=["GET", "POST"])
def write_config():
    if request.method == "POST":
        success, message = process_hub_form_data(request.form)
        return redirect(
            url_for(
                "HubPage", output=f"{'Success: ' if success else 'Error: '}{message}"
            )
        )
    return redirect(url_for("HubPage"))


@app.route("/send-hub-config", methods=["POST"])
def send_hub_config():
    try:
        # First process the form data and save locally
        success, message = process_hub_form_data(request.form)
        if not success:
            return redirect(url_for("HubPage", output=message))

        # Then send to server
        result = SendHubConfigToServer()
        if result == 0:
            return redirect(
                url_for("HubPage", output="Configuration successfully sent to server")
            )
        else:
            return redirect(
                url_for("HubPage", output="Error sending configuration to server")
            )

    except Exception as e:
        return redirect(
            url_for(
                "HubPage", output=f"Error sending configuration to server: {str(e)}"
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
                    output="Configuration successfully downloaded from server",
                )
            )
        else:
            # Redirect to /Hub with error message
            return redirect(
                url_for("HubPage", output="Error downloading configuration from server")
            )

    except Exception as e:
        # Redirect to /Hub with error message
        return redirect(
            url_for(
                "HubPage",
                output=f"Error downloading configuration from server: {str(e)}",
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

        getLogger().warning("Start InitScanners")
        # Run initScanners() to initialize scanners
        # Init Scanners before getting tokens, because this operation
        # can be completed without network
        initScanners()
        getLogger().warning("End InitScanners")

        # Run getTokens() to get authentication tokens
        getLogger().warning("Start init-hub")
        tokens_result = getTokens()
        if tokens_result != 0:
            return redirect(url_for("HubPage", output="Failed to get tokens"))

        getLogger().warning("End init-hub")
        return redirect(url_for("HubPage", output="Hub initialized successfully"))

    except (OSError, ValueError) as e:
        return redirect(url_for("HubPage", output=f"Error: {str(e)}"))


@app.route("/poweroff", methods=["POST"])
def stop_server():

    if not is_raspberry_pi():
        return render_template(
            "Hub.html",
            **updateServer(Hub),
            output="Not on Raspberry Pi",
            **get_common_template_vars()
        )

    # Before remove the USB key, we need to stop the server
    cmdeject = "sudo eject /dev/sda"
    result = run(
        cmdeject, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    getLogger().warning("Eject command: %s", cmdeject)
    if result.returncode == 0:
        getLogger().warning("SD card ejected successfully")
    else:
        getLogger().warning("SD card eject failed (return code: %d, stderr: %s)",
                          result.returncode, result.stderr)

    # Reset the verbosity level int the ConfigApp file
    # otherwise, the Raspberry Pi will not poweroff
    # if the log level stays to DEBUG
    config = ConfigApp()
    config.log_level = "WARNING"
    config.save_config()
    # On enlève également tout fichier DEBUG
    try:
        os.remove("DEBUG")
        getLogger().warning("remove_image_files: removed DEBUG")
    except (FileNotFoundError, PermissionError) as e:
        getLogger().error("Error removing file DEBUG: %s", e)

    result = run(
        "sudo poweroff", shell=True, capture_output=True, text=True, check=False
    )
    return result.stdout


if __name__ == "__main__":
    if is_prod():
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
    else:
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
