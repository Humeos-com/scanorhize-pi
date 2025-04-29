"""Application Web pour configurer les scanners"""

from subprocess import run, CalledProcessError
from time import sleep
import os

from flask import Flask, render_template, request, redirect, url_for, jsonify
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
    getHubId,
    ReadHubConfigFromServer,
    SendHubConfigToServer,
)
from ConfigApp import (
    getLogger,
    getDisplayFile,
    is_debug,
    is_prod,
    getConfigDir,
    getImageDir,
    getLogDir,
    ConfigApp,
    CONFIG_APP_FILE
)
from Miscellaneous import (
    chaineIntwitherror,
    InitGPIO,
    initDisplayFile,
    check_connectivity,
    sync_time,
)
from OSUtils import is_raspberry_pi

initDisplayFile()
getLogger().warning("Start Scanorhize.py")
Hub = HubData()
getLogger().warning("Launch Web app")
app = Flask(__name__)

has_internet = False
try:
    check_connectivity()
    has_internet = True
    getLogger().warning("Internet OK !")
    sync_time()

except RuntimeError as exc:
    getLogger().error("No internet connection: %s", exc)

# init
SSID = GetWifiSSID()
getLogger().warning("SSID: %s", SSID)
IP = GetIP()
getLogger().warning("IP: %s", IP)


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
        SSID=SSID,
        IP=IP,
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


@app.route("/Scanner/<scan_num_str>", methods=["POST", "GET"])
def ScannerPage(scan_num_str: str):
    form = request.form
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    i_scan = int(scan_num_str) - 1
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])

    if request.method == "POST":
        print("Form data:", form)

        # Update Scanner object with form data
        Scanner.resolution = ResolutionList[int(form["resolution"]) - 1] if int(form["resolution"]) <= 3 else ResolutionList[0]
        Scanner.mode = ColorList[int(form["mode"]) - 1] if form["mode"] != Scanner.mode else Scanner.mode

        # Update numeric fields with validation
        Scanner.l = chaineIntwitherror(form["l"], Scanner.l, 0, Scanner.x_max)
        Scanner.t = chaineIntwitherror(form["t"], Scanner.t, 0, Scanner.y_max)
        Scanner.x = chaineIntwitherror(form["x"], Scanner.x, 0, Scanner.x_max)
        Scanner.y = chaineIntwitherror(form["y"], Scanner.y, 0, Scanner.y_max)
        Scanner.quality = chaineIntwitherror(form["quality"], Scanner.quality, 0, 90)

        # Update other fields
        if "token" in form and form["token"] != "":
            Scanner.token = form["token"]
        Scanner.UseServer = chaineIntwitherror(form["UseServer"], Scanner.UseServer, 0, 1)
        if form["StartDate"] != "":
            Scanner.StartDate = form["StartDate"]
        Scanner.PeriodeS = parse_period(form["PeriodeS"])
        Scanner.TimeBeforeScan = chaineIntwitherror(form["TimeBeforeScan"], Scanner.TimeBeforeScan, 0, 60)
        Scanner.TimeAfterScan = chaineIntwitherror(form["TimeAfterScan"], Scanner.TimeAfterScan, 0, 60)
        Scanner.enable = 1 if "enable" in form else 0

        # Save the updated Scanner object
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])
        print("Updated Scanner object:", Scanner.__dict__)

        # Recalculate next start date
        nextStartDateValue = calculate_and_set_next_date()
        getLogger().warning("Recalculated next start date: %s", nextStartDateValue)

    Scanner.ScannerName = f"Scanner-{i_scan + 1}"
    Scannerparam = updateScanParameters(Scanner)
    Scannerparam["PeriodeS"] = format_period(Scanner.PeriodeS)
    print("Scanner n° : " + str(i_scan + 1))
    Scanner.printScanner()
    filename = str(i_scan + 1) + ".jpg"
    return render_template(
        "image.html", **Scannerparam, scan_num_str=scan_num_str, imagename=filename
    )


@app.route("/Scanner/<actionName>/<scan_num_str>", methods=["GET", "POST"])
def action(actionName: str, scan_num_str: str):
    i_scan = int(scan_num_str) - 1
    Scanner = ScannerData()
    listScannerconfigs = listConfigScanner()
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])
    print("action : ", actionName)

    # If it's a POST request, save the form data first
    if request.method == "POST" and request.form:
        getLogger().warning("Processing form data for %s", Scanner.ScannerName)
        form = request.form

        # Update Scanner object with form data (similar to ScannerPage route)
        Scanner.resolution = ResolutionList[int(form["resolution"]) - 1] if int(form["resolution"]) <= 3 else ResolutionList[0]
        Scanner.mode = ColorList[int(form["mode"]) - 1] if form["mode"] != Scanner.mode else Scanner.mode

        # Update numeric fields with validation
        Scanner.l = chaineIntwitherror(form["l"], Scanner.l, 0, Scanner.x_max)
        Scanner.t = chaineIntwitherror(form["t"], Scanner.t, 0, Scanner.y_max)
        Scanner.x = chaineIntwitherror(form["x"], Scanner.x, 0, Scanner.x_max)
        Scanner.y = chaineIntwitherror(form["y"], Scanner.y, 0, Scanner.y_max)
        Scanner.quality = chaineIntwitherror(form["quality"], Scanner.quality, 0, 90)

        # Update other fields
        if "token" in form and form["token"] != "":
            Scanner.token = form["token"]
        Scanner.UseServer = chaineIntwitherror(form["UseServer"], Scanner.UseServer, 0, 1)
        if form["StartDate"] != "":
            Scanner.StartDate = form["StartDate"]
        Scanner.PeriodeS = parse_period(form["PeriodeS"])
        Scanner.TimeBeforeScan = chaineIntwitherror(form["TimeBeforeScan"], Scanner.TimeBeforeScan, 0, 60)
        Scanner.TimeAfterScan = chaineIntwitherror(form["TimeAfterScan"], Scanner.TimeAfterScan, 0, 60)
        Scanner.enable = 1 if "enable" in form else 0

        # Save the updated Scanner object
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])
        getLogger().warning("Saved form data for %s", Scanner.ScannerName)

    output_message = None

    if actionName == "acqimg":
        InitGPIO()
        result = ScannerPreview(Scanner, i_scan)
        Scanner.LastImgFile = result[0]
        Scanner.error = result[1]
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])

    if actionName == "GetConfig":
        result = ReadScannerConfigFromServer(Scanner)
        if result == 0:
            output_message = f"Configuration successfully downloaded from server for {Scanner.ScannerName}"
        else:
            output_message = f"Error downloading configuration from server for {Scanner.ScannerName}"

    if actionName == "SendConfig":
        # First save locally to ensure we have the latest data
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])

        # Capture the command that will be executed
        hub_id = getHubId()
        command = f"s3cmd --no-preserve sync {getConfigDir()}/{Scanner.ScannerName}.json s3://hub-{hub_id}/home/pi/Scanorhize/{getConfigDir()}/{Scanner.ScannerName}.json"

        # Then send to server
        result = SendScannerConfigToServer(Scanner)

        if result == 0:
            output_message = f"Configuration successfully sent to server for {Scanner.ScannerName}\nCommand: {command}"
        else:
            output_message = f"Error sending configuration to server for {Scanner.ScannerName}\nCommand: {command}"

    # Update scanner parameters
    Scanner.ScannerName = f"Scanner-{i_scan + 1}"
    Scannerparam = updateScanParameters(Scanner)
    # Format PeriodeS for display
    Scannerparam["PeriodeS"] = format_period(Scanner.PeriodeS)

    if output_message:
        # Add the output message to the template parameters
        Scannerparam["action_output"] = output_message

    # Return the template with parameters
    return render_template(
        "image.html",
        **Scannerparam,
        scan_num_str=scan_num_str,
        imagename=f"{i_scan + 1}.jpg"
    )


@app.route("/Hub", methods=["POST", "GET"])
def HubPage():
    Hub.ReadConfig()
    # Format Hub configuration for display
    hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent}%
Temperature: {Hub.temperature}°C
Ping: {Hub.ping}"""

    if is_debug():
        hub_config += f"\nToken: {Hub.token}"

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
        todo=Hub.todo
    )


@app.route("/update_version", methods=["GET"])
def update_version():
    hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent}%
Temperature: {Hub.temperature}°C
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
        )
    try:
        getLogger().warning("Update version")
        hub_id = Hub.macAddress.replace(":", "")
        result = run(
            f"s3cmd --no-preserve sync s3://hub-{hub_id}/home/pi/Scanorhize/ /home/pi/Scanorhize/",
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
            output=result.stdout
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
        "scanorhize_server": config.scanorhize_server
    }

    return render_template("App.html", app_config=app_config)


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
            "scanorhize_server": temp_config.scanorhize_server
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

        if new_log_level not in ["WARNING", "INFO", "DEBUG"]:
            return render_template("App.html",
                                app_config=ConfigApp().__dict__,
                                output="Invalid log level value. Must be WARNING, INFO, or DEBUG.")

        # Get ConfigApp instance
        config = ConfigApp()
        config.log_level = new_log_level
        config.usb_dir = new_usb_dir

        # Save the configuration
        if config.save_config() == 0:
            # Reload the configuration to get the correct attributes
            config.load_config()
            output = f"Configuration updated successfully. Log level set to {new_log_level}"
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
            "scanorhize_server": config.scanorhize_server
        }

        return render_template("App.html", app_config=app_config, output=output)

    except Exception as e:
        return render_template("App.html",
                            app_config=ConfigApp().__dict__,
                            output=f"Error updating configuration: {str(e)}")


@app.route("/write_config", methods=["GET", "POST"])
def write_config():
    try:
        # If this is a POST request, update the Hub settings first
        if request.method == "POST":
            form = request.form
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

        # Save the Hub configuration
        Hub.WriteConfig()
        hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent} GB
Temperature: {Hub.temperature}°C
Ping: {Hub.ping}"""

        if is_debug():
            hub_config += f"\nToken: {Hub.token}"

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
            output="Configuration saved locally",
        )
    except Exception as e:
        # Recreate hub_config in the exception handler
        hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent} GB
Temperature: {Hub.temperature}°C
Ping: {Hub.ping}"""

        if is_debug():
            hub_config += f"\nToken: {Hub.token}"

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
            output=f"Error saving configuration locally: {str(e)}",
        )


@app.route("/init_hub", methods=["GET", "POST"])
def init_hub():
    getLogger().warning("Start init-hub")
    hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent}%
Temperature: {Hub.temperature}°C
Ping: {Hub.ping}"""

    if is_debug():
        hub_config += f"\nToken: {Hub.token}"
    try:
        # Run getTokens() to get authentication tokens
        tokens_result = getTokens()
        if tokens_result != 0:
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
                output="Failed to get tokens",
            )

        getLogger().warning("Start InitScanners")
        # Run initScanners() to initialize scanners
        initScanners()
        getLogger().warning("End init-hub")
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
            output="Hub initialized successfully",
        )
    except (OSError, ValueError) as e:
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
            output=f"Error: {str(e)}",
        )


@app.route("/poweroff", methods=["POST"])
def stop_server():
    result = run(
        "sudo poweroff", shell=True, capture_output=True, text=True, check=False
    )
    return result.stdout


@app.route("/send-hub-config", methods=["GET"])
def send_hub_config():
    try:
        # First ensure we have the latest config saved locally
        Hub.WriteConfig()

        # Then send to server
        result = SendHubConfigToServer()

        hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent} GB
Temperature: {Hub.temperature}°C
Ping: {Hub.ping}"""

        if is_debug():
            hub_config += f"\nToken: {Hub.token}"

        if result == 0:
            output = "Configuration successfully sent to server"
        else:
            output = "Error sending configuration to server"

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
            output=output
        )
    except Exception as e:
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
            output=f"Error sending configuration to server: {str(e)}"
        )

@app.route("/get-hub-config", methods=["GET"])
def get_hub_config():
    try:
        result = ReadHubConfigFromServer()

        hub_config = f"""Model: {Hub.model}
MAC Address: {Hub.macAddress}
Project ID: {Hub.projectId}
Battery Level: {Hub.batteryLevelPercent}%
Disk Space: {Hub.diskSpacePercent} GB
Temperature: {Hub.temperature}°C
Ping: {Hub.ping}"""

        if is_debug():
            hub_config += f"\nToken: {Hub.token}"

        if result == 0:
            output = "Configuration successfully downloaded from server"
        else:
            output = "Error downloading configuration from server"

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
            output=output
        )
    except Exception as e:
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
            output=f"Error downloading configuration from server: {str(e)}"
        )


if __name__ == "__main__":
    if is_prod():
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
    else:
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
