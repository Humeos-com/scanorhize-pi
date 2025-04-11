"""Application Web pour configurer les scanners"""

from subprocess import run, CalledProcessError
from time import sleep

from flask import Flask, render_template, request, redirect, url_for
from Scanner import (
    ScannerData,
    ScannerPreview,
    updateScanParameters,
    listConfigScanner,
    ResolutionList,
    ColorList,
)
from Server import (
    ReadConfigFromServer,
    SendConfigToServer,
    pingAPI,
    GetWifiSSID,
    GetIP,
    updateServer,
    HubData,
)
from ConfigApp import getLogger, getDisplayFile, is_debug, getConfigDir, getImageDir, getLogDir
from Miscellaneous import chaineIntwitherror, InitGPIO
from OSUtils import is_raspberry_pi

getLogger().warning("Start Scanorhize.py")

has_internet = False
tries = 0
while tries <= 10:
    if pingAPI("www.google.com"):
        has_internet = True
        break
    if is_raspberry_pi():
        sleep(5)
    tries += 1

if tries > 10:
    getLogger().error("No internet connection")
    has_internet = False
else:
    getLogger().warning("Internet connection OK.")
    has_internet = True

Server = HubData()


getLogger().warning("Launch Web app")
app = Flask(__name__)

# init
SSID = GetWifiSSID()
getLogger().warning("SSID: %s", SSID)
IP = GetIP()
getLogger().warning("IP: %s", IP)
listScannerconfigs = listConfigScanner()


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
        run(cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )

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
                sleep(1)

    return app.response_class(generate(), mimetype="text/plain")


@app.route("/Scanner/<scan_num_str>", methods=["POST", "GET"])
def ScannerPage(scan_num_str: str):
    form = request.form
    Scanner = ScannerData()
    i_scan = int(scan_num_str) - 1
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])
    if request.method == "POST":
        print(form)
        restmp = form["resolution"]
        result = int(restmp, 10)
        if result > 3:  # pas de selection
            result = 1
        Scanner.resolution = ResolutionList[result - 1]
        print(Scanner.resolution)
        modetmp = form["mode"]
        print(modetmp, " ", Scanner.mode)
        if modetmp != Scanner.mode:
            mode = int(modetmp, 10)
            Scanner.mode = ColorList[mode - 1]

        tmp = request.form["l"]
        # print("tmp=",tmp,"tmp type: ",type(tmp),"l type: ",type(Scanner.l))
        Scanner.l = chaineIntwitherror(tmp, Scanner.l, 0, 216.7)
        tmp = form["t"]
        Scanner.t = chaineIntwitherror(tmp, Scanner.t, 0, 297.5)
        tmp = form["x"]
        Scanner.x = chaineIntwitherror(tmp, Scanner.x, 0, 216.7)
        tmp = form["y"]
        Scanner.y = chaineIntwitherror(tmp, Scanner.y, 0, 297.5)
        tmp = form["quality"]
        Scanner.quality = chaineIntwitherror(tmp, Scanner.quality, 0, 90)
        tmp = form["token"]  # token vide pour non utilisation du scanner
        if tmp != "":
            Scanner.token = tmp
        tmp = form["UseServer"]
        Scanner.UseServer = chaineIntwitherror(tmp, Scanner.UseServer, 0, 1)
        tmp = form["Campaign"]  # token vide pour non utilisation du scanner
        if tmp != "":
            Scanner.Campaign = tmp
        tmp = form["StartDate"]  # token vide pour non utilisation du scanner
        if tmp != "":
            Scanner.StartDate = tmp
        tmp = form["PeriodeS"]
        Scanner.PeriodeS = chaineIntwitherror(tmp, Scanner.PeriodeS, 0, 360000)
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])
    Scanner.ScannerName = f"Scanner-{i_scan + 1}"
    Scannerparam = updateScanParameters(Scanner)
    print("Scanner n° : " + str(i_scan + 1))
    Scanner.printScanner()
    filename = str(i_scan + 1) + ".jpg"
    print(filename)
    # return render_template("image.html", form=form, imagename=filename)
    return render_template(
        "image.html", **Scannerparam, scan_num_str=scan_num_str, imagename=filename
    )


@app.route("/Scanner/<actionName>/<scan_num_str>")
def action(actionName: str, scan_num_str: str):
    i_scan = int(scan_num_str) - 1
    Scanner = ScannerData()
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])
    print("action : ", actionName)
    if actionName == "acqimg":
        InitGPIO()
        result = ScannerPreview(Scanner, i_scan)
        Scanner.LastImgFile = result[0]
        Scanner.error = result[1]
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])

    if actionName == "GetConfig":
        Scanner = ReadConfigFromServer(Scanner)
        Scanner.WriteScannerConfig(listScannerconfigs[i_scan])

    if actionName == "SendConfig":
        SendConfigToServer(Scanner)

    return redirect(url_for("ScannerPage", scan_num_str=scan_num_str))


@app.route("/Server", methods=["POST", "GET"])
def ServerPage():
    Server.ReadConfig()
    if request.method == "POST":
        Sim = 0
        tmp = request.form["apn"]
        if tmp != "":
            Server.apn = tmp
            Sim = 1
        tmp = request.form["user"]
        if tmp != "":
            Server.user = tmp
        tmp = request.form["password"]
        if tmp != "":
            Server.password = tmp
        tmp = request.form["address"]
        # Api = 0
        if tmp != "":
            Server.address = tmp
            # Api = 1

        if Sim == 1:  # modification paramètres SIM
            #### res = Connect4g()
            pass
        # if Api==1:
        Server.ping = pingAPI(Server.address)
        Server.WriteConfig()
        Server.print()

    # Format Hub configuration for display
    hub_config = f"""MAC Address: {Server.macAddress}
Project ID: {Server.projectId}
Battery Level: {Server.batteryLevelPercent}%
Disk Space: {Server.diskSpacePercent} GB
Temperature: {Server.temperature}°C
Ping: {Server.ping}"""

    if is_debug():
        hub_config += f"\nToken: {Server.token}"

    return render_template("Server.html", **updateServer(Server), hub_config=hub_config)

@app.route("/update_version", methods=["GET"])
def update_version():
    # Format Hub configuration for display
    hub_config = f"""MAC Address: {Server.macAddress}
Project ID: {Server.projectId}
Battery Level: {Server.batteryLevelPercent}%
Disk Space: {Server.diskSpacePercent} GB
Temperature: {Server.temperature}°C
Ping: {Server.ping}"""

    if is_debug():
        hub_config += f"\nToken: {Server.token}"

    if not is_raspberry_pi():
        return render_template("Server.html", **updateServer(Server), hub_config=hub_config, update_output="No update, not on Raspberry Pi")
    try:
        getLogger().warning("Update version")
        result = run(
            "s3cmd sync s3://hub-2ccf6709b478/home/pi/Scanorhize/ /home/pi/Scanorhize/",
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        return render_template("Server.html", **updateServer(Server), hub_config=hub_config, update_output=result.stdout)
    except CalledProcessError as e:
        return render_template("Server.html", **updateServer(Server), hub_config=hub_config, update_output=f"Command failed: {e.stderr}")


@app.route("/App", methods=["GET"])
def AppPage():
    # Format ConfigApp attributes for display
    app_config = f"""Config Directory: {getConfigDir()}
Image Directory: {getImageDir()}
Log Directory: {getLogDir()}
Display File: {getDisplayFile()}
Debug Mode: {is_debug()}"""

    return render_template("App.html", app_config=app_config)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=is_debug())
