#init scanner
import subprocess
from subprocess import PIPE, run
import datetime
import json
from Campaign import *
from Miscellious import *
from time import sleep
import os
ConfigScannerPath = "ConfigFile/Scanner/"

ResolutionList=["300","600","1200"]
ColorList=["Color","GRAY","Lineart"]

class ScannerData :
    ScannerName=""
    mode=ColorList[0]
    resolution=ResolutionList[0]
    LastImgTime=""
    LastImgFile=""
    l=0
    t=0
    x=216
    y=297
    quality=5
    token ="G2IGG0eedSxemoWkMeZ9p4v_I1UCvKYXkV5ObWc8ErYLNXiiPM_g5xE3qNsFMW5wLhq4YK1SmR4b19Vn66qLyA"
    UseServer=0;
    error=0;
    Campaign ="CampaignName"
    StartDate="20200810T094500Z" #next start if UseServer=1
    PeriodeS="3600"#next start if UseServer=0

Scanner=ScannerData

def updateScanParameters(Scanner) :
    global ResolutionList
    Scannerparam = {
        'scannerName' : Scanner.ScannerName,
        'mode': Scanner.mode,
        'mode1': ColorList[0],
        'mode2': ColorList[1],
        'mode3': ColorList[2],
        'resolution' : Scanner.resolution,
        'resolution1' : ResolutionList[0],
        'resolution2' : ResolutionList[1],
        'resolution3' : ResolutionList[2],
        'LastImgTime':Scanner.LastImgTime,
        'LastImgFile':Scanner.LastImgFile,
        'l':Scanner.l,
        't':Scanner.t,
        'x':Scanner.x,
        'y':Scanner.y,
        'quality' :Scanner.quality,
        'token' : Scanner.token,
        'UseServer' : Scanner.UseServer,
        'Campaign' : Scanner.Campaign,
        'StartDate' : Scanner.StartDate,
        'PeriodeS' : Scanner.PeriodeS,
        }
    return Scannerparam

ScanNumber = 3
imagetiff = "imagescan.tiff"
imagepathtiff = "/home/pi/Scanorhize/static/"+imagetiff
imagepath = "/home/pi/Scanorhize/static/"
imagepathjp2000 = imagepath+"imagejp2000.jp2"

def scanSearch():
    #function to find scanner with sane    
    res=1
    i=0
    while res!=0 and i<ScanNumber :
        cmd="sudo LD_LIBRARY_PATH=/usr/local/lib scanimage -L"
        print("i=",i)
        #print(cmd)        
        result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
        #print(result.returncode, result.stdout, result.stderr)
        res=result.returncode                       
        print(res,result.stdout)
        x=(result.stdout).split()
        #print(x)
        if x[0]=="No":
            res=1
        i+=1
    if res==0 : 
        x=(result.stdout).split("'")
        x=(result.stdout).split()
        ScannerName = x[1]
        ScannerName = ScannerName[1:len(ScannerName)-1]
    else :
        ScannerName = "NoScannerDetected"
        sleep(10)
    print("Scanner :",ScannerName)
    return ScannerName

def scanAcq(Scanner,pin,date) :
    error=TurnPin_On(pin,40)
    if error!=0:
        Scanner.error=1
        return Scanner
    Displayfile="Log/Display.txt"
    command = "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage --mode="+Scanner.mode+" --resolution="+str(Scanner.resolution)+" -l "+str(Scanner.l)+" -t "+str(Scanner.t)+" -x "+str(Scanner.x)+" -y "+str(Scanner.y)+" --format=tiff >"+imagepathtiff+" | tee -a "+Displayfile
    print(command)
    res=1
    i=0
    while res!=0 and i<2 :
        #print("i=",i)
        WriteTimeLogfile("StartScan :"+str(i))
        result = run(command, capture_output=True, universal_newlines=True, shell=True)
        WriteTimeLogfile("code: "+str(result.returncode)+"stdout :"+str(result.stdout)+"stderr :"+str(result.stderr))
        res=result.returncode
        if len(result.stderr)>2:
            res=12
        if "no SANE" in result.stderr or "Error"  in result.stderr or "failed" in result.stderr:
            res=12
        Scanner.error=res
        i+=1
        if res!=0:
            TurnPin_Off(pin)
            TurnPin_On(pin,40)

    TurnPin_Off(pin)
    if(Scanner.error>0):
        WriteTimeLogfile("error acquisition: "+result.stdout+result.stderr)
        return Scanner

    if Scanner.quality>90:
        Scanner.quality=90
    
    commandconv = "gdal_translate -of JP2OpenJPEG -co \"QUALITY="+str(Scanner.quality)+"\" "+imagepathtiff+" "+imagepathjp2000+"| tee -a "+Displayfile
    #print(commandconv)  
    WriteTimeLogfile("Start conversion jp2")
    result = run(commandconv, capture_output=True, universal_newlines=True, shell=True)
    print(result.returncode, result.stdout, result.stderr)
    Scanner.error=result.returncode
    if(Scanner.error>0):        
        WriteTimeLogfile("Error conversion jp2")
        Scanner.error=20
        return Scanner
    
    WriteTimeLogfile("EndConvTime")
    CurrentDateinS=DateToSeconds(date)+pin #Pour s'assurer que 2 images n'est pas le même temps et donc nom
    date=SecondsToDate(CurrentDateinS)
    Scanner.LastImgTime = date
    #print("image time: ",Scanner.LastImgTime)
    Scanner.LastImgFile = imagepathjp2000    
    #WriteTimeLogfile("EndscanAcqTime")
    return Scanner

def ScannerPreview(pin):
    image=str(pin+1)+".jpg"
    error=TurnPin_On(pin,40)
    if error!=0:
        Scanner.error=1
        res=Scanner.error
        return image,res    
    file=imagepath+image   
    #command = "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage -d "+Scanner.ScannerName+" --mode="+Scanner.mode+" --resolution=75"+" --format=jpeg >"+file
    command = "sudo LD_LIBRARY_PATH=/usr/local/lib scanimage --mode="+Scanner.mode+" --resolution=75"+" --format=jpeg >"+file
    #print(command)
    res=1
    i=0
    while res!=0 and i<2 :
        #print("i=",i)
        result = run(command, capture_output=True, universal_newlines=True, shell=True)
        print(result.returncode, result.stdout, result.stderr)
        res=result.returncode
        if len(result.stderr)>2:
            res=12
        i+=1
    TurnPin_Off(pin)
    if res>0:
        WriteTimeLogfile("error acquisition: "+result.stdout+result.stderr)
    else:
        WriteTimeLogfile("Preview OK")

    return image,res

def listConfigScanner():
    try :
        listfile=os.listdir(ConfigScannerPath) # returns list
        #print(listfile)
        listfile.sort(reverse=False)
        WriteTimeLogfile(listfile)
    except:
        listfile=["1-Scanner.json","2-Scanner.json","3-Scanner.json"]
    return listfile

def ReadScannerConfig(file):
    global Scanner
    fullpath=ConfigScannerPath+file
    try:
        with open(fullpath, "r") as openfile:
            data = json.load(openfile)
    except :
        WriteTimeLogfile("No file:",fullpath)
        WriteScannerConfig(Scanner,file)
    else:
        #print(data)    
        Scanner.ScannerName = data["ScannerName"]
        Scanner.mode= data["mode"]
        Scanner.resolution = data["resolution"]
        Scanner.LastImgTime= data["LastImgTime"]
        Scanner.LastImgFile= data["LastImgFile"]
        Scanner.l= data["l"]
        Scanner.t= data["t"]
        Scanner.x= data["x"]
        if Scanner.x>216:
            Scanner.x=216
        Scanner.y= data["y"]
        if Scanner.y>297:
            Scanner.y=297
        Scanner.quality =data["quality"]
        Scanner.token= data["token"]
        Scanner.UseServer=data["UseServer"]
        Scanner.Campaign=data["Campaign"]
        Scanner.StartDate=data["StartDate"]
        Scanner.PeriodeS=data["PeriodeS"]
    finally:
        printScanner(Scanner)
        return Scanner

def WriteScannerConfig(Scanner,file):
    #printScanner(Scanner)    
    data = {
        "ScannerName" : Scanner.ScannerName,
        "mode" : Scanner.mode,
        "resolution" : Scanner.resolution,
        "LastImgTime" : Scanner.LastImgTime,
        "LastImgFile" : Scanner.LastImgFile,
        "l" :Scanner.l,
        "t" :Scanner.t,
        "x" :Scanner.x,
        "y" :Scanner.y,
        "quality" :Scanner.quality,
        "token" : Scanner.token,
        "UseServer" : Scanner.UseServer,
        "Campaign" : Scanner.Campaign,
        "StartDate" : Scanner.StartDate,
        "PeriodeS" : Scanner.PeriodeS,        
        }
    try :
        #printScanner(Scanner)
        json_object = json.dumps(data, indent = len(data))
        fullpath=ConfigScannerPath+file
        #print(fullpath)
        with open(fullpath, "w") as outfile: 
            outfile.write(json_object)
    finally:
        return 0

def printScanner(scanner):
    try :
        data=scanner.ScannerName+" "+str(scanner.mode)+" "+str(scanner.resolution)+" "+str(scanner.LastImgTime)+" "+str(scanner.LastImgFile)+" "+str(scanner.l)+" "+str(scanner.t)+" "+str(scanner.x)+" "+str(scanner.y)+" "+str(Scanner.quality)+" "+str(Scanner.UseServer)+" "+str(Scanner.Campaign)+" "+str(Scanner.StartDate)+" "+str(Scanner.PeriodeS)
        print(data)
        #WriteLogFile(data)
    except:
        return 1
    return 0
