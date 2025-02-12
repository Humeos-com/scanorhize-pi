""" Application Web pour configurer les scanners """

import subprocess
from time import sleep

from flask import Flask, render_template, request, redirect, url_for
from Scanner import (
    ScannerData,
    ScannerPreview,
    updateScanParameters,
    WriteScannerConfig,
    listConfigScanner,
    ResolutionList,
    ColorList,
)
from Server import ReadConfigFromServer, pingAPI, GetWifiSSID, GetIP, updateServer, ServerData
from Miscellaneous import WriteTimeLogfile, chaineIntwitherror, InitGPIO
# from Campaign import CreateFolderImage, CopyImageToUSB, USBSpace
# from I2C import ReadBatVoltCap

LOG_DIR = "Log"
DISPLAY_FILE = LOG_DIR + "/Display.txt"

Server = ServerData()

WriteTimeLogfile("Start Scanorhize.py")

# res=""
# while res!="Scanorhize" :
#   res=GetWifiSSID()
#  sleep(10)
res = 0
while res == 0:
    res = pingAPI("www.google.com")
    sleep(5)

WriteTimeLogfile("Launch Web app")
app = Flask(__name__)

# init
SSID = GetWifiSSID()
WriteTimeLogfile(SSID)
IP = GetIP()
WriteTimeLogfile(IP)
listScannerconfigs = listConfigScanner()
i_scan = 0
# Initialisation de l'objet Scanner
#Scanner = ScannerData()
#Scanner.ReadScannerConfig(listScannerconfigs[i_scan])


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
        subprocess.call(cmd, shell=True)

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
        with open(DISPLAY_FILE, "r", encoding="utf-8") as f:
            while True:
                yield f.read()
                sleep(1)

    return app.response_class(generate(), mimetype="text/plain")


@app.route("/Scanner", methods=["POST", "GET"])
def ScannerPage():
    Scanner = ScannerData()
    #global ListScanner
    #global ResolutionList
    #global ColorList
    #global i_scan
    #global listScannerconfigs
    Scanner.ReadScannerConfig(listScannerconfigs[i_scan])
    if request.method == "POST":
        print(request.form)
        restmp = request.form["resolution"]
        result = int(restmp, 10)
        if result > 3:  # pas de selection
            result = 1
        Scanner.resolution = ResolutionList[result - 1]
        print(Scanner.resolution)
        modetmp = request.form["mode"]
        print(modetmp, " ", Scanner.mode)
        if modetmp != Scanner.mode:
            mode = int(modetmp, 10)
            Scanner.mode = ColorList[mode - 1]

        tmp = request.form["l"]
        # print("tmp=",tmp,"tmp type: ",type(tmp),"l type: ",type(Scanner.l))
        Scanner.ZoneAcq.l = chaineIntwitherror(tmp, Scanner.ZoneAcq.l, 0, 216.7)
        tmp = request.form["t"]
        Scanner.ZoneAcq.t = chaineIntwitherror(tmp, Scanner.ZoneAcq.t, 0, 297.5)
        tmp = request.form["x"]
        Scanner.ZoneAcq.x = chaineIntwitherror(tmp, Scanner.ZoneAcq.x, 0, 216.7)
        tmp = request.form["y"]
        Scanner.ZoneAcq.y = chaineIntwitherror(tmp, Scanner.ZoneAcq.y, 0, 297.5)
        tmp = request.form["quality"]
        Scanner.quality = chaineIntwitherror(tmp, Scanner.quality, 0, 90)
        tmp = request.form["token"]  # token vide pour non utilisation du scanner
        if tmp != "":
            Scanner.token = tmp
        tmp = request.form["UseServer"]
        Scanner.UseServer = chaineIntwitherror(tmp, Scanner.UseServer, 0, 1)
        tmp = request.form["Campaign"]  # token vide pour non utilisation du scanner
        if tmp != "":
            Scanner.Campaign = tmp
        tmp = request.form["StartDate"]  # token vide pour non utilisation du scanner
        if tmp != "":
            Scanner.StartDate = tmp
        tmp = request.form["PeriodeS"]
        Scanner.PeriodeS = chaineIntwitherror(tmp, Scanner.PeriodeS, 0, 360000)
        WriteScannerConfig(Scanner, listScannerconfigs[i_scan])
    Scanner.ScannerName = "Scanner" + str(i_scan + 1)
    Scannerparam = updateScanParameters(Scanner)
    print("Scanner n° : " + str(i_scan + 1))
    Scanner.printScanner()
    filename = str(i_scan + 1) + ".jpg"
    print(filename)
    return render_template("image.html", **Scannerparam, imagename=filename)


@app.route("/Scanner1", methods=["POST", "GET"])
def Scanner1():
    global i_scan
    i_scan = 0
    return redirect(url_for("ScannerPage"))


@app.route("/Scanner2", methods=["POST", "GET"])
def Scanner2():
    global i_scan
    i_scan = 1
    return redirect(url_for("ScannerPage"))


@app.route("/Scanner3", methods=["POST", "GET"])
def Scanner3():
    global i_scan
    i_scan = 2
    return redirect(url_for("ScannerPage"))


@app.route("/Scanner/<deviceName>")
def action(deviceName):
    Scanner = ScannerData()
    #global Campaign
    #global i_scan
    # Scannerparam = updateScanParameters(Scanner)
    # filename = ""
    print("devicename : ", deviceName)
    if deviceName == "acqimg":
        InitGPIO()
        result = ScannerPreview(i_scan)
        Scanner.LastImgFile = result[0]
        Scanner.error = result[1]
        WriteScannerConfig(Scanner, listScannerconfigs[i_scan])

    if deviceName == "GetConfig":
        Scanner = ReadConfigFromServer(Scanner)
        WriteScannerConfig(Scanner, listScannerconfigs[i_scan])
    # Scannerparam = updateScanParameters(Scanner)

    return redirect(url_for("ScannerPage"))


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
        #Api = 0
        if tmp != "":
            Server.address = tmp
            #Api = 1

        if Sim == 1:  # modification paramètres SIM
            #### res = Connect4g()
            pass
        # if Api==1:
        Server.ping = pingAPI(Server.address)
        Server.WriteConfig()
        Server.print()

    return render_template("Server.html", **updateServer(Server))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
