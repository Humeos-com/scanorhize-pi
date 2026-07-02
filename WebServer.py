#!/usr/bin/env python3
"""Application Web pour configurer les scanners"""

import os
import sys
import threading
import uuid
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
    scanAcq,
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
    set_default_on,
    is_mc_connected,
    is_WittyPi_3,
    is_WittyPi_4,
    is_WittyPi_5,
    parse_wittypi_time,
    get_rtc_timestamp,
    get_sys_timestamp,
    system_to_rtc,
    network_to_rtc,
    wp5_sync,
    set_startup_time,
    set_shutdown_time,
    get_fw_revision,
    get_power_cut_delay,
    set_power_cut_delay,
    get_power_priority,
    set_power_priority,
    get_usb_voltage,
    get_input_voltage,
    get_output_voltage,
    get_output_current,
    get_low_voltage_threshold,
    get_recovery_voltage_threshold,
    set_recovery_voltage_threshold,
    safeShutdown,
    pre_shutdown_checks,
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

# In-memory store for async test jobs: task_id -> {"status": "running"/"done", "result": {...}}
_test_tasks: dict = {}
_test_tasks_lock = threading.Lock()
_active_tests: set = set()  # test names currently running


def get_common_template_vars():
    """Get common variables for templates with fresh hub_info"""
    mc = is_mc_connected()
    wittypi_times = {"connected": mc, "shutdown": None, "wakeup": None, "shutdown_iso": None, "wakeup_iso": None}
    if mc:
        from datetime import datetime
        try:
            s = parse_wittypi_time(get_shutdown_time())
            if s:
                wittypi_times["shutdown"] = s.strftime("%-d %b %H:%M:%S")
                wittypi_times["shutdown_iso"] = s.isoformat() + "Z"
        except Exception:
            pass
        try:
            w = parse_wittypi_time(get_startup_time())
            if w:
                wittypi_times["wakeup"] = w.strftime("%-d %b %H:%M:%S")
                wittypi_times["wakeup_iso"] = w.isoformat() + "Z"
        except Exception:
            pass
    return {
        "SSID": GetWifiSSID(),
        "IP": GetIP(),
        "hub_info": get_hub_info(),
        "SSH_PORT": getSSHPort(),
        "version": __version__,
        "wittypi": wittypi_times,
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
    with _test_tasks_lock:
        if test_name in _active_tests:
            return jsonify(error="busy", message=f"Test '{test_name}' is already running"), 409
        _active_tests.add(test_name)
        task_id = str(uuid.uuid4())
        _test_tasks[task_id] = {"status": "running", "result": None, "messages": []}

    def worker():
        with app.app_context():
            try:
                resp = _run_test_impl(test_name, task_id)
                result = resp.get_json() or {}
            except Exception as e:
                result = {"ok": False, "message": str(e)}
        ok = result.get("ok", False)
        processing = result.get("processing", False)
        msg = result.get("message", "").replace("\n", " ")[:120]
        getLogger().info("Test %s: %s — %s", test_name, "PASS" if ok else ("IN PROGRESS" if processing else "FAIL"), msg)
        with _test_tasks_lock:
            _active_tests.discard(test_name)
            _test_tasks[task_id]["status"] = "done"
            _test_tasks[task_id]["result"] = result

    getLogger().info("Test: %s (task %s)", test_name, task_id)
    threading.Thread(target=worker, daemon=True).start()
    return jsonify(task_id=task_id)


@app.route("/tests/status/<task_id>", methods=["GET"])
def test_status(task_id: str):
    with _test_tasks_lock:
        task = _test_tasks.get(task_id)
    if task is None:
        return jsonify(status="not_found"), 404
    messages = task.get("messages", [])
    if task["status"] == "running":
        return jsonify(status="running", messages=messages)
    return jsonify(status="done", messages=messages, **task["result"])


@app.route("/tests/ping", methods=["GET"])
def tests_ping():
    return jsonify(ok=True)


@app.route("/api/wittypi-times", methods=["GET"])
def api_wittypi_times():
    mc = is_mc_connected()
    result = {"connected": mc, "shutdown": None, "wakeup": None, "shutdown_iso": None, "wakeup_iso": None}
    if mc:
        try:
            s = parse_wittypi_time(get_shutdown_time())
            if s:
                result["shutdown"] = s.strftime("%-d %b %H:%M:%S")
                result["shutdown_iso"] = s.isoformat() + "Z"
        except Exception:
            pass
        try:
            w = parse_wittypi_time(get_startup_time())
            if w:
                result["wakeup"] = w.strftime("%-d %b %H:%M:%S")
                result["wakeup_iso"] = w.isoformat() + "Z"
        except Exception:
            pass
    return jsonify(result)


@app.route("/api/clock-status", methods=["GET"])
def api_clock_status():
    import socket, struct, time as time_mod
    result = {"rtc_diff": None, "rtc_ok": None, "ntp_diff": None, "ntp_ok": None}
    try:
        rtc_ts = get_rtc_timestamp()
        sys_ts = get_sys_timestamp()
        if rtc_ts != -1:
            diff = abs(rtc_ts - sys_ts)
            result["rtc_diff"] = round(diff, 1)
            result["rtc_ok"] = diff <= 10
    except Exception:
        pass
    try:
        NTP_DELTA = 2208988800
        packet = b'\x1b' + 47 * b'\0'
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(5)
        s.sendto(packet, ("pool.ntp.org", 123))
        data, _ = s.recvfrom(1024)
        s.close()
        ntp_time = struct.unpack('!12I', data)[10] - NTP_DELTA
        diff = abs(time_mod.time() - ntp_time)
        result["ntp_diff"] = round(diff, 1)
        result["ntp_ok"] = diff <= 10
    except Exception:
        pass
    return jsonify(result)


@app.route("/api/sync-rtc", methods=["POST"])
def api_sync_rtc():
    if not is_mc_connected():
        return jsonify(ok=False, message="WittyPi not connected", detail="")
    data = request.get_json(silent=True) or {}
    option = int(data.get("option", 3))
    if option not in (1, 2, 3):
        return jsonify(ok=False, message="Invalid option", detail="")
    labels = {1: "system→RTC", 2: "RTC→system", 3: "network sync"}
    ok, detail = wp5_sync(option, timeout=10)
    message = f"Option {option} ({labels[option]}): {'OK' if ok else 'FAILED'}"
    return jsonify(ok=ok, message=message, detail=detail)


@app.route("/tests/cancel/<task_id>", methods=["POST"])
def cancel_test(task_id: str):
    with _test_tasks_lock:
        if task_id in _test_tasks:
            _test_tasks[task_id]["cancelled"] = True
    return jsonify(ok=True)


def _task_is_cancelled(task_id: str) -> bool:
    with _test_tasks_lock:
        task = _test_tasks.get(task_id)
        return task is not None and task.get("cancelled", False)


def _task_log(task_id, message):
    with _test_tasks_lock:
        if task_id in _test_tasks:
            _test_tasks[task_id].setdefault("messages", []).append(message)


def _run_test_impl(test_name: str, task_id: str = None):
    try:
        # ── CONNECTIVITY ──────────────────────────────────────────────────────

        # Hotspot SSID: verify hub_AP SSID matches Humeos_{wlan0 mac}
        if test_name == "hotspot-ssid":
            mac = open("/sys/class/net/wlan0/address").read().strip().replace(":", "")
            expected = f"Humeos_{mac}"
            actual = GetWifiSSID()
            if actual == expected:
                return jsonify(ok=True, message=f"Hotspot SSID: {actual}", summary="Hotspot SSID OK")
            return jsonify(ok=False, message=f"SSID mismatch — expected: {expected}, got: {actual}", summary="Hotspot SSID FAIL")

        # Internet: one connectivity probe
        if test_name == "internet":
            try:
                check_connectivity(3)
                return jsonify(ok=True, message="Internet connection is available.", summary="Internet OK")
            except RuntimeError as e:
                return jsonify(ok=False, message=str(e), summary="Internet FAIL")

        # S3: check production bucket is reachable, then chain to the humeos-test bucket.
        # Two-step chain so each bucket gets its own PASS/FAIL line in the console.
        if test_name == "s3":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="S3: no internet")
            config = ConfigApp()
            result = run(
                f"s3cmd ls {config.s3_bucket}",
                shell=True, capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                return jsonify(ok=True, message=f"S3 bucket {config.s3_bucket} is accessible using `s3cmd`.", next_test="s3-test")
            return jsonify(ok=False, message=result.stderr or "Could not reach {config.s3_bucket} bucket.", summary=f"S3 FAIL ({config.s3_bucket})")

        # S3-test: second step of the S3 chain — verify the humeos-test bucket used by speed test
        if test_name == "s3-test":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="S3-test: no internet")
            config = ConfigApp()
            result = run(
                f"s3cmd ls s3://humeos-test",
                shell=True, capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                return jsonify(ok=True, message=f"S3 bucket s3://humeos-test is accessible using `s3cmd`.", summary=f"S3 OK ({config.s3_bucket} + humeos-test)")
            return jsonify(ok=False, message=result.stderr or "Could not reach s3://humeos-test bucket.", summary="S3 FAIL (humeos-test)")

        # SSH: verify reverse tunnel process exists and TCP connection is established
        if test_name == "ssh":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="SSH: no internet")
            server = getScanorhizeServer()
            ssh_port = getSSHPort()
            procs = run("pgrep -a ssh", shell=True, capture_output=True, text=True, check=False)
            tunnel_lines = [l for l in procs.stdout.splitlines() if f"-R {ssh_port}" in l or f"-R{ssh_port}" in l]
            if not tunnel_lines:
                return jsonify(ok=False, message=f"No SSH reverse tunnel process found (expected -R {ssh_port}).\nAll ssh processes:\n{procs.stdout or '(none)'}", summary="SSH tunnel: no process")
            ss = run(f"ss -tn state established dst {server}", shell=True, capture_output=True, text=True, check=False)
            if server not in ss.stdout:
                return jsonify(ok=False, message=f"Tunnel process exists but TCP connection to {server} is not ESTABLISHED.\nProcess: {tunnel_lines[0]}\nss output:\n{ss.stdout}", summary="SSH tunnel: not connected")
            return jsonify(ok=True, message=f"Reverse tunnel active and connected to {server}:{ssh_port}\nProcess: {tunnel_lines[0]}", summary="SSH tunnel active")

        # Upload-pictures-service: verify the systemd upload-pictures service is running.
        # If active, chains to copy-test-picture to actually exercise the upload pipeline.
        if test_name == "upload-pictures-service":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="Upload service: no internet")
            from Campaign import getUsbDir
            usb_dir = getUsbDir()
            if is_raspberry_pi() and not os.path.ismount(usb_dir):
                return jsonify(
                    ok=False,
                    message=f"USB drive not found at {usb_dir} — insert the USB drive and retry",
                    summary="Upload service: no USB drive",
                )

            try:
                result = run(
                    ["systemctl", "is-active", "upload-pictures"],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip() == "active":
                    return jsonify(ok=True, message="Upload Pictures service is active.", next_test="copy-test-picture")
                else:
                    return jsonify(ok=False, message=f"Upload Pictures service status: {result.stdout.strip()}", summary=f"Upload service: {result.stdout.strip()}")
            except Exception as e:
                return jsonify(ok=False, message="Upload Pictures service status is not 'active'", summary="Upload service: not active")

        # Copy-test-picture: plant a dummy jpg in the USB image folder so the upload service
        # picks it up. Uses the first scanner config that has both projectId and sampleId,
        # since they all share the same S3 destination. Chains to wait-for-pictures-upload.
        if test_name == "copy-test-picture":
            configs = listConfigScanner()
            if not configs:
                return jsonify(ok=False, message="No scanner config files found.", summary="Upload: no scanner config")
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
                        now = datetime.now().strftime("%H:%M:%S")
                        return jsonify(ok=True, message=f"Test file {testFile} copied to {destFile}\n[{now}] <b style='color:orange;'>⌛ IN PROGRESS</b>: Test picture is waiting to be uploaded to server", next_test="wait-for-pictures-upload")
                    except FileNotFoundError:
                        return jsonify(ok=False, message=f"Test file {testFile} not found.", summary="Upload: test file not found")
                    except Exception as e:
                        return jsonify(ok=False, message=str(e), summary="Upload: copy failed")
            return jsonify(ok=False, message="No scanner config files found.", summary="Upload: no scanner config")

        # Wait-for-pictures-upload: sum files across all scanner folders, re-schedule itself via
        # next_test until the count reaches zero (upload service has moved them all to S3).
        # processing=True keeps the IN PROGRESS line visible and suppresses duplicate messages
        # when the file count hasn't changed between polls.
        if test_name == "wait-for-pictures-upload":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="Upload: no internet")
            configs = listConfigScanner()
            if not configs:
                return jsonify(ok=False, message="No scanner config files found.", summary="Upload: no scanner config")
            total_files = 0
            for cfg in configs:
                scanner = ScannerData()
                scanner.ReadScannerConfig(cfg)
                if scanner.projectId and scanner.sampleId:
                    destination = Path(f"/media/pi/Image/{scanner.projectId}/{scanner.sampleId}")
                    if destination.exists():
                        total_files += sum(1 for f in destination.iterdir() if f.is_file())
            if total_files == 0:
                return jsonify(ok=True, message="Test files (.json, .jpg and .jp2) uploaded to server (no more files in folder)", summary="Upload OK")
            else:
                file_word = 'file' if total_files == 1 else 'files'
                return jsonify(processing=True, message=f"Uploading {total_files} {file_word} to server", next_test="wait-for-pictures-upload")

        # Speed: measure download then upload throughput against a fixed 2 MB file on S3.
        # Each direction is reported as an intermediate message while polling so the user
        # sees download speed before the upload finishes. Cancellation is checked between
        # the two transfers — it can't interrupt a running s3cmd subprocess.
        if test_name == "speed":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="Speed: no internet")
            import time
            local_path = "/tmp/2MB.jpg"
            s3_path = "s3://humeos-test/tests/2MB.jpg"
            try:
                _task_log(task_id, "⬇ Downloading 2MB test file…")
                t0 = time.time()
                run(["s3cmd", "--force", "get", s3_path, local_path], check=True)
                t1 = time.time()
                download_time = t1 - t0
                size_bytes = os.path.getsize(local_path)
                download_speed = (size_bytes / (1024 * 1024)) / download_time
                _task_log(task_id, f"⬇ Download: {download_time:.2f}s ({download_speed:.2f} MB/s) — uploading…")
                # Cancellation point: between download and upload (only place we can safely stop)
                if _task_is_cancelled(task_id):
                    return jsonify(ok=False, message="Test stopped by user", summary="Speed test: stopped")
                t2 = time.time()
                run(["s3cmd", "put", local_path, s3_path], check=True)
                t3 = time.time()
                upload_time = t3 - t2
                upload_speed = (size_bytes / (1024 * 1024)) / upload_time
                summary = (
                    f"Download: {download_time:.2f}s ({download_speed:.2f} MB/s) | "
                    f"Upload: {upload_time:.2f}s ({upload_speed:.2f} MB/s)"
                )
                return jsonify(
                    ok=True,
                    message=f"⬆ Upload: {upload_time:.2f}s ({upload_speed:.2f} MB/s)",
                    summary=summary,
                )
            except Exception as e:
                return jsonify(ok=False, message=str(e), summary="Speed test FAIL")

        # ── HARDWARE ──────────────────────────────────────────────────────────

        # 4G: query modem state and SIM via ModemManager (mmcli); passes if state == connected
        if test_name == "4g":
            # ModemManager holds the serial ports open — use mmcli to query through it
            list_result = run(
                "mmcli -L", shell=True, capture_output=True, text=True, check=False
            )

            if list_result.returncode != 0 or "No modems were found" in list_result.stdout:
                return jsonify(
                    ok=False,
                    message="No 4G modem detected (mmcli -L).\nIs ModemManager running?",
                    summary="4G: no modem detected",
                )

            # Parse modem path
            modem_path = list_result.stdout.strip().splitlines()[0].split()[0]
            modem_index = modem_path.split("/")[-1]

            detail = run(
                f"mmcli -m {modem_index} --output-keyvalue",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )

            detail_out = detail.stdout if detail.returncode == 0 else list_result.stdout

            def mmcli_field(key):
                for line in detail_out.splitlines():
                    line = line.strip()

                    if ":" not in line:
                        continue

                    k, v = line.split(":", 1)

                    if k.strip() == key:
                        return v.strip()

                return ""

            state    = mmcli_field("modem.generic.state")
            operator = mmcli_field("modem.3gpp.operator-name")
            tech     = mmcli_field("modem.generic.access-technologies")
            signal   = mmcli_field("modem.generic.signal-quality.value")
            sim_path = mmcli_field("modem.generic.sim")
            unlock   = mmcli_field("modem.generic.unlock-required")

            # Query SIM details
            sim_iccid = None
            sim_active = None

            if sim_path and sim_path != "--":
                sim_index = sim_path.split("/")[-1]

                sim_result = run(
                    f"mmcli -i {sim_index} --output-keyvalue",
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if sim_result.returncode == 0:

                    def sim_field(key):
                        for line in sim_result.stdout.splitlines():
                            line = line.strip()

                            if ":" not in line:
                                continue

                            k, v = line.split(":", 1)

                            if k.strip() == key:
                                return v.strip()

                        return ""

                    sim_iccid = sim_field("sim.properties.iccid")
                    sim_active = sim_field("sim.properties.active")

            connected = state.lower() == "connected"

            lines = [f"\n  → State: {state}" if state else "\n  → State: unknown"]

            if sim_path and sim_path != "--":
                lines.append("  → SIM: present")

                # ✔ FIX: suppress false SIM-PIN2 noise
                # PIN2 is NOT required for data connection
                if unlock and unlock != "--" and unlock not in ["sim-pin2"]:
                    lines.append(f"  → SIM status: waiting for {unlock}")
                elif unlock == "sim-pin2":
                    lines.append("  → SIM status: PIN2 available (not required)")

                if sim_active:
                    lines.append(f"  → SIM active: {sim_active}")

                if sim_iccid:
                    lines.append(f"  → ICCID: {sim_iccid}")

            else:
                lines.append("  → SIM: not detected")

            if operator and operator != "--":
                lines.append(f"  → Operator: {operator}")

            if tech and tech != "--":
                lines.append(f"  → Technology: {tech}")

            if signal and signal != "--":
                lines.append(f"  → Signal quality: {signal}%")

            summary = state

            # ✔ FIX: remove misleading PIN2 from summary unless actually blocking
            if unlock and unlock != "--" and unlock not in ["sim-pin2"]:
                summary += f" – waiting for {unlock}"

            elif operator and operator != "--":
                summary += f" – {operator}"

            if signal and signal != "--":
                summary += f" {signal}%"

            return jsonify(
                ok=connected,
                message="\n".join(lines),
                summary=summary,
            )
    
        # Timezone: UTC check + internet time accuracy via NTP
        if test_name == "timezone":
            try:
                check_connectivity(3)
            except RuntimeError as e:
                return jsonify(ok=False, message=f"No internet connection: {e}", summary="Timezone: no internet")
            import socket, struct, time as time_mod
            lines_out = []
            all_ok = True

            # --- Check 1: timezone is UTC ---
            td = run("timedatectl", shell=True, capture_output=True, text=True, check=False)
            if td.returncode != 0:
                return jsonify(ok=False, message=f"timedatectl failed: {td.stderr}", summary="Timezone: timedatectl failed")
            timezone = ""
            for line in td.stdout.splitlines():
                if "Time zone" in line:
                    timezone = line.split(":", 1)[1].strip()
                    break
            tz_upper = timezone.upper()
            is_utc = (tz_upper.startswith("UTC") or tz_upper.startswith("ETC/UTC")
                      or tz_upper.startswith("ETC/UCT") or "+0000" in timezone)
            if not is_utc:
                all_ok = False
            lines_out.append(f"\n  → Timezone: {'OK' if is_utc else 'FAIL'} ({timezone})")

            # --- Check 2: NTP drift ≤ 2s ---
            try:
                NTP_DELTA = 2208988800  # seconds between 1900-01-01 and 1970-01-01
                packet = b'\x1b' + 47 * b'\0'  # NTP client request
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(5)
                s.sendto(packet, ("pool.ntp.org", 123))
                data, _ = s.recvfrom(1024)
                s.close()
                ntp_time = struct.unpack('!12I', data)[10] - NTP_DELTA
                drift = abs(time_mod.time() - ntp_time)
                ntp_ok = drift <= 10
                if not ntp_ok:
                    all_ok = False
                lines_out.append(f"  → Time vs NTP: {'OK' if ntp_ok else 'FAIL'} ({drift:.2f}s difference)")
            except Exception as e:
                all_ok = False
                lines_out.append(f"  → Time vs NTP: ERROR ({e})")

            return jsonify(
                ok=all_ok,
                message="\n".join(lines_out),
                summary=f"Timezone: {timezone}" if timezone else "Timezone: unknown",
            )

        # WittyPi: check I2C presence, model, firmware version, default-on flag, RTC/system
        # clock drift, and next scheduled alarms. Fails if: default-on is OFF (255), startup
        # alarm is too soon (<3 min) or suspiciously far (>20 days), or RTC differs from
        # system clock by more than 2 seconds.
        if test_name == "on-off":
            if not is_mc_connected():
                return jsonify(ok=False, message="ON/OFF management board not detected on I2C bus.", summary="ON/OFF management board: not detected")

            if is_WittyPi_5():
                model = "WittyPi 5"
            elif is_WittyPi_4():
                model = "WittyPi 4"
            elif is_WittyPi_3():
                model = "WittyPi 3"
            else:
                model = "WittyPi (unknown version)"

            try:
                startup = parse_wittypi_time(get_startup_time())
            except Exception:
                startup = None
            try:
                shutdown = parse_wittypi_time(get_shutdown_time())
            except Exception:
                shutdown = None

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

            default_on_raw = get_default_on()  # 0=immediately on, 255=stay off

            if default_on_raw != 250:
                _prev = default_on_raw
                if set_default_on(250) and get_default_on() == 250:
                    default_on_raw = 250
                    _prev_str = "OFF" if _prev == 255 else f"{_prev}s"
                    default_on = f"Turn ON after 250s <i style='color:orange'>(updated from {_prev_str})</i>"
                else:
                    _prev_str = "OFF" if _prev == 255 else f"{_prev}s"
                    default_on = f"<b style='font-weight:bold; color:red;'>⚠ {_prev_str} (update to 250s failed)</b>"
            else:
                default_on = "Turn ON after 250s"

            from datetime import timedelta
            warning_text = ""
            startup_warning = ""
            startup_reschedule_note = ""
            shutdown_warning = ""
            shutdown_reschedule_note = ""

            # --- Startup (wakeup) reschedule ---
            reschedule = False
            reschedule_reason = ""
            if not startup:
                reschedule = True
                reschedule_reason = "not set"
            else:
                delta = startup - now
                if delta < timedelta(minutes=3):
                    startup_warning = " <b style='color:red; font-weight:bold;'>⚠ too soon (&lt;3 min)</b>"
                    reschedule = True
                    reschedule_reason = "too soon"
                elif delta > timedelta(days=20):
                    startup_warning = " <b style='color:red;font-weight:bold;'>⚠ too far (&gt;20 days - probably in the past)</b>"
                    reschedule = True
                    reschedule_reason = "too far"
            if reschedule:
                new_wakeup = now + timedelta(minutes=22)
                set_startup_time(new_wakeup.day, new_wakeup.hour, new_wakeup.minute, 0)
                expected_str = f"{new_wakeup.day:02d} {new_wakeup.hour:02d}:{new_wakeup.minute:02d}:00"
                readback_str = get_startup_time()
                if readback_str == expected_str:
                    startup = new_wakeup.replace(second=0, microsecond=0)
                    startup_warning = ""
                    startup_reschedule_note = f" <i style='color:orange;'>(rescheduled from {reschedule_reason} → +22 min)</i>"
                    startup_left = startup - now
                    startup_left_str = str(startup_left).split('.')[0]
                else:
                    return jsonify(
                        ok=False,
                        summary=f"{model} FAIL",
                        message=(
                            f"\n  ⚠ Startup time was {reschedule_reason} and reschedule to "
                            f"{new_wakeup.strftime('%H:%M')} failed.\n"
                            f"  → Expected: {expected_str}\n"
                            f"  → Readback: {readback_str}"
                        ),
                    )

            # --- Shutdown reschedule ---
            sd_reschedule = False
            sd_reschedule_reason = ""
            if not shutdown:
                sd_reschedule = True
                sd_reschedule_reason = "not set"
            else:
                sd_delta = shutdown - now
                if sd_delta < timedelta(minutes=3):
                    shutdown_warning = " <b style='color:red; font-weight:bold;'>⚠ too soon (&lt;3 min)</b>"
                    sd_reschedule = True
                    sd_reschedule_reason = "too soon"
                elif sd_delta > timedelta(days=20):
                    shutdown_warning = " <b style='color:red;font-weight:bold;'>⚠ too far (&gt;20 days - probably in the past)</b>"
                    sd_reschedule = True
                    sd_reschedule_reason = "too far"
            if sd_reschedule:
                new_shutdown = now + timedelta(minutes=20)
                set_shutdown_time(new_shutdown.day, new_shutdown.hour, new_shutdown.minute, 0)
                sd_expected_str = f"{new_shutdown.day:02d} {new_shutdown.hour:02d}:{new_shutdown.minute:02d}:00"
                sd_readback_str = get_shutdown_time()
                if sd_readback_str == sd_expected_str:
                    shutdown = new_shutdown.replace(second=0, microsecond=0)
                    shutdown_warning = ""
                    shutdown_reschedule_note = f" <i style='color:orange;'>(rescheduled from {sd_reschedule_reason} → +20 min)</i>"
                    shutdown_left = shutdown - now
                    shutdown_left_str = str(shutdown_left).split('.')[0]
                else:
                    return jsonify(
                        ok=False,
                        summary=f"{model} FAIL",
                        message=(
                            f"\n  ⚠ Shutdown time was {sd_reschedule_reason} and reschedule to "
                            f"{new_shutdown.strftime('%H:%M')} failed.\n"
                            f"  → Expected: {sd_expected_str}\n"
                            f"  → Readback: {sd_readback_str}"
                        ),
                    )

            try:
                if startup and shutdown:
                    gap = startup - shutdown
                    if gap.total_seconds() < 0:
                        warning_text = "\n  → <b style='font-weight:bold; color:red;'>⚠ WARNING</b>:        Next wakeup occurs BEFORE next shutdown."
                    elif gap.total_seconds() < 120:
                        warning_text = f"\n  → <b style='font-weight:bold; color:orange;'>⚠ WARNING</b>:        Gap between shutdown and wakeup is only {int(gap.total_seconds())}s (min 2 min recommended)."
            except Exception:
                warning_text = ""

            shutdown_str = f"{shutdown}" + (f" ({shutdown_left_str} left)" if shutdown else "") if shutdown else "<span style='color:red; font-weight:bold;'>⚠ not set</span>"
            shutdown_str += shutdown_warning + shutdown_reschedule_note
            startup_str  = f"{startup}"  + (f" ({startup_left_str} left)"  if startup  else "") if startup  else "<span style='color:red; font-weight:bold;'>⚠ not set</span>"
            startup_str += startup_warning + startup_reschedule_note

            from datetime import timezone as tz
            rtc_ts = get_rtc_timestamp()
            sys_ts = get_sys_timestamp()
            rtc_warning = False
            sys_date_str = datetime.fromtimestamp(sys_ts, tz=tz.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            if rtc_ts == -1:
                rtc_time_str = "<span style='color:orange; font-weight:bold;'>⚠ RTC time unavailable</span>"
                rtc_date_str = "N/A"
                rtc_warning = True
            else:
                time_diff = abs(rtc_ts - sys_ts)
                rtc_date_str = datetime.fromtimestamp(rtc_ts, tz=tz.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                if time_diff > 10:
                    sync_ok, sync_detail = system_to_rtc()
                    sleep(2)
                    new_rtc_ts = get_rtc_timestamp()
                    new_diff = abs(new_rtc_ts - get_sys_timestamp()) if new_rtc_ts != -1 else 9999
                    if new_diff <= 10:
                        rtc_date_str = datetime.fromtimestamp(new_rtc_ts, tz=tz.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                        rtc_time_str = f"<span style='color:green;'>✔ synced (was {time_diff}s off, now {new_diff}s)</span>"
                    else:
                        rtc_date_str = datetime.fromtimestamp(new_rtc_ts, tz=tz.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if new_rtc_ts != -1 else "N/A"
                        rtc_time_str = f"<b style='color:red; font-weight:bold;'>⚠ sync {'OK' if sync_ok else 'failed'} — was {time_diff}s off, still {new_diff}s off — {sync_detail}</b>"
                        rtc_warning = True
                else:
                    rtc_time_str = f"OK ({time_diff}s difference)"

            fw_rev = get_fw_revision()
            try:
                fw_parts = tuple(int(x) for x in fw_rev.split(".")) if fw_rev else (0,)
                fw_too_old = fw_parts < (1, 4)
            except (ValueError, AttributeError):
                fw_parts = (0,)
                fw_too_old = True
            if fw_too_old:
                fw_str = f"<b style='color:red; font-weight:bold;'>⚠ v{fw_rev} (too old, min 1.4)</b>"
            else:
                fw_str = f"v{fw_rev}" if fw_rev is not None else "unknown"

            power_cut_delay = get_power_cut_delay()
            power_cut_delay_warning = power_cut_delay is not None and power_cut_delay != 10
            if power_cut_delay is None:
                power_cut_str = "unknown"
            elif power_cut_delay_warning:
                old_delay = power_cut_delay
                if set_power_cut_delay(10) and get_power_cut_delay() == 10:
                    power_cut_delay = 10
                    power_cut_delay_warning = False
                    power_cut_str = f"10s <i style='color:orange;'>(was {old_delay}s, updated to 10s)</i>"
                else:
                    power_cut_str = f"<b style='color:red; font-weight:bold;'>⚠ {power_cut_delay}s (expected 10s — update failed)</b>"
            else:
                power_cut_str = f"{power_cut_delay}s"

            power_priority = get_power_priority()  # 0=Vusb first, 1=Vin first
            power_priority_warning = False
            if power_priority is None:
                power_priority_str = "unknown"
            elif power_priority not in (0, 1):
                power_priority_warning = True
                power_priority_str = f"<b style='color:red; font-weight:bold;'>⚠ unexpected value: {power_priority} (expected 0 or 1)</b>"
            elif power_priority != 1:  # 1 = Vin first (expected), 0 = Vusb first
                if set_power_priority(1):
                    power_priority_str = "Vin first <i style='color:orange;'>(was Vusb first, updated)</i>"
                else:
                    power_priority_warning = True
                    power_priority_str = "<b style='color:red; font-weight:bold;'>⚠ Vusb first (expected Vin first — update failed)</b>"
            else:
                power_priority_str = "Vin first"

            recovery_v = get_recovery_voltage_threshold()
            recovery_v_warning = False
            if recovery_v is None:
                recovery_v_str = "unknown"
            elif recovery_v != 10.0:
                old_rv = recovery_v
                set_recovery_voltage_threshold(100)  # 100 = 10.0V
                new_rv = get_recovery_voltage_threshold()
                if new_rv == 10.0:
                    recovery_v_str = f"10.0V <i style='color:orange;'>(was {old_rv:.1f}V, updated)</i>"
                else:
                    recovery_v_warning = True
                    recovery_v_str = f"<b style='color:red; font-weight:bold;'>⚠ {old_rv:.1f}V (expected 10.0V — update failed)</b>"
            else:
                recovery_v_str = "10.0V"

            vin  = get_input_voltage()
            vusb = get_usb_voltage()
            usb_powered = vusb > 1.0 and vin < 1.0
            power_str = (
                f"<b style='color:orange;font-weight:bold;'>⚠ USB ({vusb:.2f}V) — not on battery</b>"
                if usb_powered else
                f"Vin {vin:.2f}V"
            )

            ok = bool(startup and shutdown and not startup_warning and default_on_raw != 255 and not rtc_warning and not power_cut_delay_warning and not fw_too_old and not power_priority_warning and not recovery_v_warning)
            return jsonify(
                ok=ok,
                summary=f"{model} {'OK' if ok else 'FAIL'}",
                message=(
                    f"\n"
                    f"  → Model:            {model}\n"
                    f"  → Firmware:         {fw_str}\n"
                    f"  → Power source:     {power_str}\n"
                    f"  → Power priority:   {power_priority_str}\n"
                    f"  → Recovery voltage: {recovery_v_str}\n"
                    f"  → Default on power: {default_on}\n"
                    f"  → Power cut delay:  {power_cut_str}\n"
                    f"  → RTC vs system:    {rtc_time_str}\n"
                    f"      → RTC:          {rtc_date_str}\n"
                    f"      → System:       {sys_date_str}\n"
                    f"  → Next <span style='color:orange'>shutdown</span>:    {shutdown_str}\n"
                    f"  → Next <span style='color:green'>wakeup</span>:      {startup_str}"
                    f"{warning_text}"
                ),
            )

        # Wittypi-cycle: schedule a shutdown in ~1 min and a wakeup 1 min later, then return
        # immediately with processing=True. The frontend countdown timer pings /tests/ping
        # after the expected wakeup time to verify the Pi came back up. The flag file
        # wittypi_test_mode forces the app into config mode on next boot so the cycle test
        # page is shown again automatically after reboot.
        if test_name == "off-on-cycle":
            if not is_mc_connected():
                return jsonify(ok=False, message="ON/OFF management board not detected on I2C bus.", summary="ON/OFF management board cycle: not detected")

            from datetime import datetime, timedelta
            now = datetime.now()
            # Skip to the minute after next if we're too close to the next minute boundary
            seconds_to_next = 60 - now.second
            shutdown = now.replace(second=0, microsecond=0) + timedelta(minutes=1 if seconds_to_next >= 15 else 2)
            wakeup   = shutdown + timedelta(minutes=1)

            # Flag file presence tells the boot sequence to stay in test/config mode
            Path("wittypi_test_mode").write_text("")

            set_shutdown_time(shutdown.day, shutdown.hour, shutdown.minute, 0)
            set_startup_time(wakeup.day,   wakeup.hour,   wakeup.minute,   0)

            # Verify the values were actually stored in I2C registers
            shutdown_expected = f"{shutdown.day:02d} {shutdown.hour:02d}:{shutdown.minute:02d}:00"
            wakeup_expected   = f"{wakeup.day:02d} {wakeup.hour:02d}:{wakeup.minute:02d}:00"
            shutdown_readback = get_shutdown_time()
            wakeup_readback   = get_startup_time()
            if shutdown_readback != shutdown_expected or wakeup_readback != wakeup_expected:
                Path("wittypi_test_mode").unlink(missing_ok=True)
                return jsonify(
                    ok=False,
                    summary="OFF/ON cycle: I2C write verification failed",
                    message=(
                        f"\n  ⚠ I2C readback mismatch — times were not stored correctly.\n"
                        f"  → Shutdown expected: {shutdown_expected}  got: {shutdown_readback}\n"
                        f"  → Wakeup expected:   {wakeup_expected}  got: {wakeup_readback}"
                    ),
                )

            getLogger().info(
                "OFF/ON cycle test: shutdown at %s, wakeup at %s",
                shutdown.strftime("%H:%M:%S"), wakeup.strftime("%H:%M:%S")
            )
            return jsonify(
                ok=True,
                processing=True,
                message=(
                    f"\n  → Test <span style='color:orange;'>shutdown</span>:    {shutdown.strftime('%H:%M:%S')}\n"
                    f"  → Test <span style='color:green;'>wakeup</span>:      {wakeup.strftime('%H:%M:%S')}"
                ),
                shutdown_in=(shutdown - now).total_seconds(),
                wakeup_in=(wakeup - now).total_seconds(),
            )

        # Scanners-config-files: audit all scanner JSON configs and the live SANE device list.
        # A scanner counts as "configured" (expectedScanners) if it has a projectId or sampleId,
        # and as "ready" (configuredScanners) only if its device is also currently plugged in.
        # Fails on any of: no ready scanners, missing devices, projectId mismatch across scanners,
        # duplicate sampleIds, or a projectId set without a matching sampleId.
        if test_name == "scanners-config-files":
            configs = listConfigScanner()
            if not configs:
                return jsonify(ok=False, message="No scanner config files found.")
            # Query live SANE device list once; skip on non-Pi (dev/test environment)
            connected_devices = ScannerData().scanSearchAll() if is_raspberry_pi() else None
            lines = []
            configuredScanners = 0  # scanners with projectId/sampleId AND device plugged in
            expectedScanners = 0    # scanners with projectId or sampleId (intended to be active)
            projectIds = []
            sampleIds = []
            missing_sample_ids = []  # configs where projectId is set but sampleId is empty
            for cfg in configs:
                scanner = ScannerData()
                scanner.ReadScannerConfig(cfg)
                if scanner.projectId or scanner.sampleId:
                    expectedScanners += 1
                    if scanner.projectId:
                        projectIds.append(scanner.projectId)
                    if scanner.sampleId:
                        sampleIds.append(scanner.sampleId)
                    elif scanner.projectId:
                        missing_sample_ids.append(cfg)
                    if not scanner.device or scanner.device == "NoScannerDetected":
                        device_str = "<span style='font-weight:bold; color:orange;'>⚠</span> device missing or not detected"
                    elif connected_devices is not None and scanner.device not in connected_devices:
                        device_str = f"<span style='font-weight:bold; color:orange;'>⚠</span> not plugged in ({scanner.device})"
                    else:
                        device_str = scanner.device
                        configuredScanners += 1
                    lines.append(f"\n  → {cfg}:\n    - projectId: {scanner.projectId}\n    - sampleId:  {scanner.sampleId}\n    - device:    {device_str}")
                else:
                    lines.append(f"\n  → {cfg}: Empty config file")

            n = len(lines)
            scanner_word = 'scanner' if configuredScanners == 1 else 'scanners'
            project_ids_match = len(set(projectIds)) <= 1
            sample_ids_unique = len(sampleIds) == len(set(sampleIds))
            no_missing_sample_ids = len(missing_sample_ids) == 0
            ok = configuredScanners > 0 and configuredScanners >= expectedScanners and project_ids_match and sample_ids_unique and no_missing_sample_ids
            # Show the most actionable failure reason first
            if configuredScanners == 0:
                suffix = f"\n\n  → No scanner configured"
                summary = "Scanners: no scanner configured"
            elif configuredScanners < expectedScanners:
                missing = expectedScanners - configuredScanners
                suffix = f"\n\n  → {configuredScanners}/{expectedScanners} {scanner_word} configured — {missing} missing device"
                summary = f"Scanners: {configuredScanners}/{expectedScanners} — {missing} missing device"
            elif not project_ids_match:
                unique = ', '.join(set(projectIds))
                suffix = f"\n\n  → <b style='color:orange;'>⚠ projectId mismatch: {unique}</b>"
                summary = f"Scanners: projectId mismatch"
            elif not sample_ids_unique:
                dupes = [sid for sid in set(sampleIds) if sampleIds.count(sid) > 1]
                suffix = f"\n\n  → <b style='color:orange;'>⚠ duplicate sampleId: {', '.join(dupes)}</b>"
                summary = f"Scanners: duplicate sampleId"
            elif not no_missing_sample_ids:
                suffix = f"\n\n  → <b style='color:orange;'>⚠ projectId set but sampleId missing: {', '.join(missing_sample_ids)}</b>"
                summary = f"Scanners: sampleId missing"
            else:
                suffix = f"\n\n  → {configuredScanners} {scanner_word} configured"
                summary = f"{configuredScanners} {scanner_word} configured"
            return jsonify(ok=ok, message="Scanner configs found:\n" + "\n".join(lines) + suffix, summary=summary)

        # Take-pictures: inlined scan loop (instead of subprocess) so we can emit per-scanner
        # progress messages while polling. Chains to wait-for-pictures-upload on success.
        if test_name == "take-pictures":
            from Campaign import CopyImageToUSB, CreateFolderOnUSB, USBSpace, getUsbDir
            from DateUtils import GetCurrentDate

            usb_dir = getUsbDir()
            if is_raspberry_pi() and not os.path.ismount(usb_dir):
                return jsonify(
                    ok=False,
                    message=f"USB drive not found at {usb_dir} — insert the USB drive and retry",
                    summary="Take pictures: no USB drive",
                )
            usb_free_mb, usb_free_pct, _ = USBSpace()

            configs = listConfigScanner()
            enabled = []       # scanners with enable=1 (connected at app startup)
            expected_count = 0  # scanners with a projectId or sampleId in their config
            for i, cfg in enumerate(configs):
                s = ScannerData()
                s.ReadScannerConfig(cfg)
                if s.projectId or s.sampleId:
                    expected_count += 1
                if s.enable:
                    enabled.append((i, cfg, s))

            total = len(enabled)
            # Fail if no scanner was detected at startup
            if total == 0:
                return jsonify(ok=False, message="No scanner found", summary="Take pictures: no scanner")
            # Fail if fewer scanners are enabled than the config expects
            # (catches scanners that were disconnected before the app started)
            if total < expected_count:
                return jsonify(
                    ok=False,
                    message=f"Only {total}/{expected_count} scanner(s) connected — check scanners-config-files test for details",
                    summary=f"Take pictures: {total}/{expected_count} scanners connected",
                )

            current_date = GetCurrentDate()
            pictures_taken = 0
            scanning_error = 0
            scanner_ids = []

            for idx, (i_scan, cfg, scanner) in enumerate(enabled):
                # Allow the stop button to interrupt between scans
                if _task_is_cancelled(task_id):
                    return jsonify(ok=False, message="Test stopped by user", summary="Take pictures: stopped")
                # Fresh SANE device list before each scan to catch scanners unplugged mid-test.
                # sleep(5) gives the scanner time to recover after the SANE query before scanimage runs.
                if is_raspberry_pi():
                    live_devices = ScannerData().scanSearchAll()
                    if scanner.device not in live_devices:
                        return jsonify(
                            ok=False,
                            message=f"Scanner {idx + 1}/{total} not plugged in ({scanner.device})",
                            summary=f"Take pictures: scanner {idx + 1} not plugged in",
                        )
                    sleep(5)
                _task_log(task_id, f"📷 Taking picture {idx + 1}/{total}…")
                scanner_ids.append(f"{scanner.projectId}/{scanner.sampleId}")
                scanner = scanAcq(scanner, i_scan, current_date)
                scanner.WriteScannerConfig(cfg)
                if scanner.error == 0:
                    sleep(5)  # brief pause before USB copy (matches TakePictures.py behaviour)
                    folder = CreateFolderOnUSB(scanner.projectId)
                    folder = CreateFolderOnUSB(os.path.join(folder, scanner.sampleId))
                    copy_error = CopyImageToUSB(scanner, folder, prefix="test")
                    if copy_error == 0:
                        _task_log(task_id, f"  ✓ Picture {idx + 1}/{total} saved to USB")
                        pictures_taken += 1
                    else:
                        _task_log(task_id, f"  ⚠ Picture {idx + 1}/{total}: copy to USB failed")
                        scanning_error = 1
                else:
                    return jsonify(
                        ok=False,
                        message=f"Scan error on picture {idx + 1}/{total}",
                        summary=f"Take pictures: scan error {idx + 1}/{total}",
                    )

            scanner_list = "\n    - ".join(scanner_ids)
            pic_word = 'picture' if pictures_taken == 1 else 'pictures'
            ok = scanning_error == 0 and pictures_taken > 0 and pictures_taken == total
            return jsonify(
                ok=ok,
                message=f"{pictures_taken}/{total} {pic_word} taken\n  → USB free: {usb_free_mb} MB ({usb_free_pct}%)\n  → Scanners:\n    - {scanner_list}",
                **({'next_test': 'wait-for-pictures-upload'} if ok else {}),
                summary=f"{pictures_taken}/{total} {pic_word} taken",
            )
            

        # Wittypi-cycle-cancel: called by the frontend stop button during a cycle test.
        # Removes the flag file so the next boot won't force test mode, and arms a safety
        # shutdown 20 minutes out in case the Pi reboots into an unexpected state.
        if test_name == "wittypi-cycle-cancel":
            flag = Path("wittypi_test_mode")

            from datetime import datetime, timedelta
            now = datetime.now()
            safety = now.replace(second=0, microsecond=0) + timedelta(minutes=20)
            set_shutdown_time(safety.day, safety.hour, safety.minute, 0)

            if flag.exists():
                flag.unlink()
                return jsonify(
                    ok=True,
                    message=(
                        f"Cycle test flag file removed.\n"
                        f"  → Safety shutdown: {safety.strftime('%H:%M:%S')} (now + 20 min)"
                    )
                )
            return jsonify(
                ok=True,
                message=(
                    f"Cycle test flag file already gone.\n"
                    f"  → Safety shutdown: {safety.strftime('%H:%M:%S')} (now + 20 min)"
                )
            )

        # Ping: simple liveness check used by the wittypi-cycle monitor after reboot
        # Battery: read WittyPi input/output voltage and current
        if test_name == "battery":
            if not is_mc_connected():
                return jsonify(ok=False, message="ON/OFF management board not detected — cannot read battery voltage.", summary="Battery: ON/OFF management board not detected")

            vin  = get_input_voltage()
            vusb = get_usb_voltage()
            vout = get_output_voltage()
            iout = get_output_current()
            low_v      = get_low_voltage_threshold()
            recovery_v = get_recovery_voltage_threshold()

            # Determine power source
            usb_powered = vusb > 1.0 and vin < 1.0
            if usb_powered:
                power_source = "<b style='color:orange;font-weight:bold;'>USB (5V)</b>"
                ok = True  # USB power is valid, just not a field deployment
            else:
                power_source = "Battery"
                ok = vin >= 10.0

            if usb_powered:
                vin_str = f"{vusb:.2f}V (USB)"
            elif vin < 10.0:
                vin_str = f"<b style='color:red;font-weight:bold;'>⚠ {vin:.2f}V (critical)</b>"
            elif vin < 11.5:
                vin_str = f"<b style='color:orange;font-weight:bold;'>⚠ {vin:.2f}V (low)</b>"
            else:
                vin_str = f"{vin:.2f}V"

            return jsonify(
                ok=ok,
                summary=f"Battery {'OK' if ok else 'FAIL'} ({'USB' if usb_powered else f'{vin:.2f}V'})",
                message=(
                    f"\n"
                    f"  → Power source:           {power_source}\n"
                    f"  → Input voltage (Vin):    {vin_str}\n"
                    f"  → USB voltage (Vusb):     {vusb:.2f}V\n"
                    f"  → Output voltage (Vout):  {vout:.2f}V\n"
                    f"  → Output current (Iout):  {iout:.3f}A\n"
                    f"  → Low voltage threshold:  {low_v:.1f}V\n"
                    f"  → Recovery threshold:     {recovery_v:.1f}V"
                ),
            )

        # MPPT: read Victron MPPT data via VE.Direct USB cable
        if test_name == "mppt":
            try:
                from MPPT_utilities import read_mppt, read_config, MPPTReader
            except ImportError:
                return jsonify(ok=False, message="MPPT_utilities not available.", summary="MPPT: not available")

            port = MPPTReader.find_vedirect_port()
            if port is None:
                return jsonify(ok=False, message="No VE.Direct port detected. Is the USB cable plugged in?", summary="MPPT: not detected")

            try:
                frame = read_mppt(port=port, timeout=10.0)
            except TimeoutError:
                return jsonify(ok=False, message=f"No data from MPPT on {port} within 10s.", summary="MPPT: no data")

            try:
                config        = read_config(port=port, timeout=10.0)
                config_checks = config.check_lifepo4_12v(capacity_ah=6.0)
                config_error  = None
            except Exception as _cfg_exc:
                config        = None
                config_checks = []
                config_error  = str(_cfg_exc)

            config_ok = all(s != "fail" for s, _, _ in config_checks)

            FW_MIN = 174
            try:
                fw_int = int(frame.firmware_version) if frame.firmware_version else 0
            except (ValueError, TypeError):
                fw_int = 0
            fw_display = f"{fw_int / 100:.2f}" if fw_int else (frame.firmware_version or "?")
            fw_ok = fw_int >= FW_MIN
            fw_str = (
                f"<b style='color:red;font-weight:bold;'>⚠ v{fw_display} (min v{FW_MIN / 100:.2f} → Update Victron firmware version using <a target='_blank' href=''>VictronConnect</a>)</b>"
                if not fw_ok else f"v{fw_display}"
            )

            ok = frame.error in (None, "No error") and config_ok and fw_ok
            panel_disconnected = (frame.panel_voltage is not None and frame.panel_voltage < 0.1)

            batt_v_raw = frame.battery_voltage
            if batt_v_raw is not None:
                if batt_v_raw < 12.2:
                    batt_v = f"<b style='color:orange;font-weight:bold;'>⚠ {batt_v_raw:.2f}V (low)</b>"
                else:
                    batt_v = f"{batt_v_raw:.2f}V"
            else:
                batt_v = "N/A"

            panel_v = f"{frame.panel_voltage:.2f}V" if frame.panel_voltage is not None else "N/A"
            panel_w = f"{frame.panel_power}W"        if frame.panel_power   is not None else "N/A"

            if config_error:
                config_msg = f"\n  → Config check:      failed — {config_error}\n"
            elif config_checks:
                _icons = {"ok": "<b style='color:green;'>✔</b>",
                          "warn": "<b style='color:orange;font-weight:bold;'>⚠</b>",
                          "fail": "<b style='color:red;font-weight:bold;'>✘</b>"}
                config_msg = "\n  ── LiFePO4 12.8V / 6Ah config ──\n"
                for status, label, detail in config_checks:
                    config_msg += f"  → {label:<22} {_icons[status]} {detail}\n"
            else:
                config_msg = "\n  → Config check:      N/A (no registers responded)\n"

            return jsonify(
                ok=ok,
                panel_disconnected=panel_disconnected,
                summary=f"MPPT {'OK' if ok else 'FAIL'} ({frame.charge_state})",
                message=(
                    f"\n"
                    f"  → Port:              {port}\n"
                    f"  → Battery voltage:   {batt_v}\n"
                    f"  → Panel voltage:     {panel_v}\n"
                    f"  → Panel power:       {panel_w}\n"
                    f"  → Charge state:      {frame.charge_state}\n"
                    f"  → MPPT mode:         {frame.mppt_mode}\n"
                    f"  → Error:             {frame.error or 'None'}\n"
                    f"  → Yield today:       {frame.yield_today} kWh\n"
                    f"  → Yield total:       {frame.yield_total} kWh\n"
                    f"  → Firmware:          {fw_str}\n"
                    + config_msg
                ),
            )

        if test_name == "ping":
            return jsonify(ok=True, message="Server is up.")

        return jsonify(ok=False, message=f"Unknown test: {test_name}")

    except Exception as e:
        getLogger().error("Test %s exception: %s", test_name, e)
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
                    "ON/OFF management board wakeup updated after schedule change: %s", next_wakeup
                )
            except Exception as e:
                getLogger().error(
                    "Error updating ON/OFF management board wakeup after schedule change: %s", e
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


@app.route("/set-wakeup", methods=["POST"])
def set_wakeup():
    if not is_mc_connected():
        return jsonify(ok=False, message="WittyPi not connected."), 400
    data = request.get_json(silent=True) or {}
    minutes = data.get("minutes")
    if not minutes or int(minutes) <= 0:
        return jsonify(ok=False, message="Invalid duration."), 400
    from datetime import datetime, timedelta
    target = datetime.now() + timedelta(minutes=int(minutes))
    try:
        set_startup_time(target.day, target.hour, target.minute, 0)
    except Exception as e:
        return jsonify(ok=False, message=f"Failed to set wakeup time: {e}"), 500
    getLogger().info("Wakeup time set to %s via poweroff modal", target.strftime("%d %H:%M"))
    return jsonify(ok=True, message=f"Wakeup set for day {target.strftime('%d at %H:%M')}")


@app.route("/api/pre-shutdown", methods=["POST"])
def api_pre_shutdown():
    if not is_mc_connected():
        return jsonify(ok=True, message="WittyPi not connected — no checks needed")
    try:
        pre_shutdown_checks()
    except Exception as e:
        return jsonify(ok=False, message=f"Pre-shutdown checks failed: {e}")
    priority = get_power_priority()
    wakeup = parse_wittypi_time(get_startup_time())
    issues = []
    if priority != 1:
        issues.append(f"power priority is {priority} (expected 1)")
    if not wakeup:
        issues.append("no wakeup time set")
    if issues:
        return jsonify(ok=False, message="Issues remain after fixes: " + "; ".join(issues))
    return jsonify(ok=True, message=f"System ready — wakeup: {wakeup.strftime('%-d %b %H:%M')}, power priority: Vin first")


@app.route("/poweroff", methods=["POST"])
def stop_server():

    if not is_raspberry_pi():
        return render_template(
            "Hub.html",
            output=sanitize_output("Not on Raspberry Pi"),
            **get_common_template_vars(),
        )

    # Block shutdown if no wakeup is set or is more than 2 days away
    force = (request.get_json(silent=True) or {}).get("force", False)
    if is_mc_connected() and not force:
        from datetime import datetime, timedelta
        try:
            startup = parse_wittypi_time(get_startup_time())
        except Exception:
            startup = None
        if not startup:
            return jsonify(ok=False, force_allowed=False, message="No wakeup time set on the WittyPi — set one before powering off."), 400
        if startup > datetime.now() + timedelta(days=2):
            return jsonify(ok=False, force_allowed=True, message=f"Wakeup time is too far away ({startup.strftime('%d %H:%M')}) — set a wakeup within the next 2 days, or power off anyway."), 400

    # Reset log level — if left at DEBUG the Pi won't power off
    config = ConfigApp()
    config.log_level = "WARNING"
    config.save_config()
    try:
        os.remove("DEBUG")
    except (FileNotFoundError, PermissionError):
        pass

    safeShutdown()
    return jsonify(ok=True, message="Hub is powering off...")


if __name__ == "__main__":
    if is_prod():
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
    else:
        # Run Flask in production mode for background execution
        app.run(host="0.0.0.0", port=8080, debug=is_debug(), use_reloader=is_debug())
