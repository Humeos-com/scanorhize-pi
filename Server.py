#connection avec API serveur
import os
import subprocess
from subprocess import PIPE, run
import json
from time import sleep
from Scanner import *
from Campaign import *
from Miscellious import *
  
        
def ReadConfigFromServer(Scanner):
    cmdRead = "curl --max-time 60 -X GET \"https://preprod.scanorhize.com/api/scanner/configuration\" -H \"accept: application/json\" -H \"scanner:"+Scanner.token+ "\""
    print(cmdRead)    
    result = run(cmdRead, capture_output=True, universal_newlines=True, shell=True)
    print(result.returncode, result.stdout, result.stderr)
    if (result.returncode)==0:
        try:
            data = json.loads(result.stdout)
            WriteTimeLogfile("Config server: "+result.stdout)        
            if "name" in data:
                Scanner.Campaign = data["name"]
            if "startDate" in data:            
                Scanner.StartDate = data["startDate"]
            if "periode" in data:
                Scanner.PeriodeS= data["periode"]
            if "mode" in data:
                Scanner.mode=data["mode"]
            if "t" in data:
                Scanner.t=data["t"]
            if "l" in data:
                Scanner.l=data["l"]
            if "x" in data:
                Scanner.x=data["x"]
            if "y" in data:
                Scanner.y=data["y"]
            if "resolution" in data:
                Scanner.resolution=data["resolution"]
            if "quality" in data:
                Scanner.quality=data["quality"]
            WriteTimeLogfile("json recu : "+data)
        except :
            WriteTimeLogfile("Error reading json")
    else:
        WriteTimeLogfile("Config server error: "+result.stderr)    
    return Scanner

def PostImageToServer(Scanner):
    error=0
    Displayfile="Log/Display.txt"    
    Date=Scanner.LastImgTime
    Resolution=Scanner.resolution    
    token=Scanner.token
    ImagePath=CreateTempImage(Scanner)
    cmdPost ="sudo curl --max-time 60 -X POST \"https://preprod.scanorhize.com/api/scanner/image\" -H \"accept: */*\" -H \"scanner: "+token+"\" -H \"Content-Type: multipart/form-data\" -F \"date="+Date+"\" -F \"dpi="+str(Resolution)+"\" -F \"file=@"+ImagePath+"\""
    print(cmdPost)              
    result = run(cmdPost, capture_output=True, universal_newlines=True, shell=True)
    #print(result.returncode, result.stdout, result.stderr)
    if(result.returncode!=0):
        WriteTimeLogfile("Post return: "+str(result.returncode)+"stdout :"+str(result.stdout)+" error: "+str(result.stderr))
        error=1
    RemoveTempImage(ImagePath)
    return error

def SendParameters(Scanner,battery,diskspace,temperature):    
    #print(battery,diskspace,temperature)
    Displayfile="Log/Display.txt"
    token=Scanner.token    
    cmdPUT ="sudo curl --max-time 60 -X PUT \"https://preprod.scanorhize.com/api/scanner/state?battery="+str(battery)+"&diskSpace="+str(diskspace)+"&temperature="+str(temperature)+"\""+" -H \"accept: */*\" -H \"scanner: "+token+"\""
    print(cmdPUT)              
    result = run(cmdPUT, capture_output=True, universal_newlines=True, shell=True)
    #print(result.returncode, result.stdout, result.stderr)
    if(result.returncode!=0):
        WriteTimeLogfile("Put return: "+str(result.returncode)+" error: "+result.stderr)    
    return 0


def GetWifiSSID():
    
    cmd = "sudo iwgetid"        
    result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
    #print(result.returncode, result.stdout, result.stderr)
    x=(result.stdout).split("\"")
    #print(x)
    SSID = x[1]
    #print(SSID)
    return SSID
def GetIP():
    
    cmd = "hostname -I"        
    result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
    #print(result.returncode, result.stdout, result.stderr)
    x=(result.stdout).split()
    #print(x)
    IP = x[0]
    #print(IP)
    return IP
def pingAPI(address):
    try :
        response=os.system("ping -c 1 "+address)
        #print("address: ",address,"response : ",response)
    except :
        response=1
    if response==0 :
        print("Ping OK")
        return 1
    else:
        print("Ping Error")
        return 0
