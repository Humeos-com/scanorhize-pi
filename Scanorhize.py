from flask import Flask, render_template, request, redirect, url_for
import datetime
import subprocess
from time import sleep

from Scanner import *
from Server import *
from Miscellious import *
from Campaign import *
from I2C import *

WriteTimeLogfile("Start Scanorhize.py")

#res=""
#while res!="Scanorhize" :
 #   res=GetWifiSSID()
  #  sleep(10)
res=0
while res==0:
    res=pingAPI("www.google.com")
    sleep(10)

WriteTimeLogfile("Launch Web app")
app = Flask(__name__)

#init
global Server
SSID = GetWifiSSID()
WriteTimeLogfile(SSID)
IP = GetIP()
WriteTimeLogfile(IP)
global Scanner
listScannerconfigs=listConfigScanner()
i_scan=0
Scanner=ReadScannerConfig(listScannerconfigs[i_scan]) 

#This function does not allow caching of images from browser
@app.after_request
def add_header(response):
    #print("add_header", response)
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

@app.route("/",methods=["POST","GET"])
def index():
    if request.method =="POST" :
        cmd="sudo pkill -f ScanorhizeProcess.py"
        subprocess.call(cmd,shell=True)
                
    return render_template('index.html', ScannerID= "001", imagename1="1.jpg",imagename2="2.jpg",imagename3="3.jpg",SSID=SSID, IP=IP)

@app.route('/stream')
def stream():
    def generate():
        with open('/home/pi/Scanorhize/Log/Display.txt') as f:
            while True:
                yield f.read()                
                sleep(1)

    return app.response_class(generate(), mimetype='text/plain')


@app.route("/Scanner", methods=["POST","GET"])
def ScannerPage():
    global Scanner
    global ListScanner
    global ResolutionList
    global ColorList
    global i_scan
    global listScannerconfigs
    Scanner=ReadScannerConfig(listScannerconfigs[i_scan])
    if request.method =="POST" :
        print(request.form)
        restmp = request.form["resolution"]
        res=int(restmp,10)
        if res>3 : #pas de selection
            res=1    
        Scanner.resolution=ResolutionList[res-1]
        print(Scanner.resolution)
        modetmp = request.form["mode"]
        print(modetmp, " ",Scanner.mode)
        if modetmp != Scanner.mode :
            mode=int(modetmp,10)        
            Scanner.mode=ColorList[mode-1]
            
        tmp = request.form["l"]
        #print("tmp=",tmp,"tmp type: ",type(tmp),"l type: ",type(Scanner.l))
        Scanner.l=chaineIntwitherror(tmp, Scanner.l,0,216.7)
        tmp = request.form["t"]        
        Scanner.t=chaineIntwitherror(tmp, Scanner.t,0,297.5)
        tmp = request.form["x"]        
        Scanner.x=chaineIntwitherror(tmp, Scanner.x,0,216.7)
        tmp = request.form["y"]        
        Scanner.y=chaineIntwitherror(tmp, Scanner.y,0,297.5)
        tmp = request.form["quality"]        
        Scanner.quality=chaineIntwitherror(tmp, Scanner.quality,0,90)
        tmp=request.form["token"]   #token vide pour non utilisation du scanner     
        if tmp!="":
            Scanner.token = tmp
        tmp = request.form["UseServer"]        
        Scanner.UseServer=chaineIntwitherror(tmp, Scanner.UseServer,0,1)
        tmp=request.form["Campaign"]   #token vide pour non utilisation du scanner     
        if tmp!="":
            Scanner.Campaign = tmp
        tmp=request.form["StartDate"]   #token vide pour non utilisation du scanner     
        if tmp!="":
            Scanner.StartDate = tmp
        tmp = request.form["PeriodeS"]        
        Scanner.PeriodeS=chaineIntwitherror(tmp, Scanner.PeriodeS,0,360000)
        WriteScannerConfig(Scanner,listScannerconfigs[i_scan])
    Scanner.ScannerName="Scanner"+str(i_scan+1)
    Scannerparam = updateScanParameters(Scanner)
    print("Scanner n° : "+str(i_scan+1))
    printScanner(Scanner)   
    filename = str(i_scan+1)+".jpg"
    print(filename)
    return render_template('image.html',**Scannerparam,imagename=filename)
@app.route("/Scanner1", methods=["POST","GET"])
def Scanner1():
    global i_scan
    i_scan=0
    return redirect(url_for('ScannerPage'))
@app.route("/Scanner2", methods=["POST","GET"])
def Scanner2():
    global i_scan
    i_scan=1
    return redirect(url_for('ScannerPage'))
@app.route("/Scanner3", methods=["POST","GET"])
def Scanner3():
    global i_scan
    i_scan=2
    return redirect(url_for('ScannerPage'))

@app.route("/Scanner/<deviceName>")
def action(deviceName):
    global Scanner
    global Campaign
    global i_scan
    Scannerparam = updateScanParameters(Scanner)
    filename=""
    print("devicename : ",deviceName)
    if deviceName == 'acqimg':
        InitGPIO()        
        result=ScannerPreview(i_scan)
        Scanner.LastImgFile=result[0]
        Scanner.error=result[1]        
        WriteScannerConfig(Scanner,listScannerconfigs[i_scan])                     
                
    if deviceName == 'GetConfig':
        Scanner = ReadConfigFromServer(Scanner)
        WriteScannerConfig(Scanner,listScannerconfigs[i_scan])
    Scannerparam=updateScanParameters(Scanner)
       
    return redirect(url_for('ScannerPage'))

@app.route("/Server",methods=["POST","GET"])
def ServerPage():
    global Server
    if request.method =="POST" :
        Sim=0
        tmp=request.form["apn"]        
        if tmp!="":
            Server.apn = tmp
            Sim=1
        tmp=request.form["user"]
        Server.user = tmp            
        tmp=request.form["password"]
        Server.password = tmp 
        tmp=request.form["address"]
        Api=0
        if tmp!="":
            Server.address = tmp
            Api=1                         
        
            
        if Sim==1:# modification paramètres SIM
            res=Connect4g()
        #if Api==1:
        Server.ping=pingAPI(Server.address)
        WriteSeverConfig(Server)
        printServer(Server)
        return render_template('Server.html', **updateServer(Server))
    else :
        print("else")
        return render_template('Server.html',**updateServer(Server))
    

if __name__ == "__main__":    
    app.run(host='0.0.0.0', port=8080, debug=False)
    
   