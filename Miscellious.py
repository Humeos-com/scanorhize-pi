# miscellious functions
from Scanner import *
#from Server import *
from Campaign import *
import datetime
import RPi.GPIO as GPIO
import subprocess
from time import sleep

Ch1Pin = 19
Ch2Pin = 26
Ch3Pin = 20
Ch4Pin = 21
PinArray =[Ch1Pin,Ch2Pin,Ch3Pin,Ch4Pin]

def chaineIntwitherror(chaine, valueerror,valuemin, valuemax):
    try :
        tmp=int(chaine,10)
    except :
        tmp=valueerror
    if tmp<valuemin :
        tmp=valuemin
    if tmp>valuemax :
       tmp=valuemax
    return tmp
def checkchaine(chaine, valueerror):
    tmp=isinstance(chaine,str)
    print("is a chaine: ",tmp)
    if tmp==True:
        return chaine
    else:
        return valueerror
def WriteLogFile(data):
    print(data)
    try:
        now = datetime.datetime.utcnow()
        filename=now.strftime("Log/Scanorhize_%Y-%m-%d.txt")
        f=open(filename, "a")
        f.write(data)
        f.write("\r\n")
        f.close()
    except:
        return 1
    return 0
def initDisplayFile():
    try:
        filename="Log/Display.txt"
        f=open(filename, "w")
        f.write("")
        f.close()
    except:
        return 1  
    return 0
def WriteDisplayFile(data,time):
    try :
        #print(data)    
        filename="Log/Display.txt"
        f=open(filename, "a")    
        text=time+" : "+str(data)
        f.write(text)
        f.write("\r\n")
        f.close()
    except:
        return 1
    return 0

def WriteTimeLogfile(data):
    date=GetCurrentDate()
    try :        
        Time=date+" : "+str(data)
        WriteLogFile(Time)
        WriteDisplayFile(data,date)
    finally:
        return date

def WriteBatterieFile(Volt,Cap):
    try:
        print(Volt," ",Cap)
        date=GetCurrentDate()
    except :
        return 1
    try :
        filename="Log/Batterie.txt"
        f=open(filename, "a")    
        text=date+": "+str(Volt)+" "+str(Cap)
        f.write(text)
        f.write("\r\n")
        f.close()
    except:
        return 1
    return 0

def InitGPIO():
    try:
        GPIO.setwarnings(False)       
        GPIO.setmode(GPIO.BCM) 
        GPIO.setup(Ch1Pin, GPIO.OUT)#Scanner1    
        GPIO.setup(Ch2Pin, GPIO.OUT)#Scanner2    
        GPIO.setup(Ch3Pin, GPIO.OUT)#Scanner3    
        GPIO.setup(Ch4Pin, GPIO.OUT)#Clé 4g 
        GPIO.output(Ch1Pin, GPIO.HIGH) 
        GPIO.output(Ch2Pin, GPIO.HIGH)
        GPIO.output(Ch3Pin, GPIO.HIGH)
    except:
        return 1
    #GPIO.output(Ch4Pin, GPIO.HIGH)
    return 0
def TurnUSBPin_On(pin,time):   
    
    cmd = "echo '1-1'|sudo tee /sys/bus/usb/drivers/usb/unbind"
    res = subprocess.call(cmd,shell=True)
    TurnPin_On(pin,1)    
    cmd = "echo '1-1'|sudo tee /sys/bus/usb/drivers/usb/bind"
    res = subprocess.call(cmd,shell=True)
    sleep(time)
    return 0
def TurnPin_On(pin,time):    
    try:
        realpin=PinArray[pin]    
        GPIO.output(realpin, GPIO.LOW)
        sleep(time)
    except :
       return 1
    return 0
def TurnPin_Off(pin):
    try :
        realpin=PinArray[pin]
        GPIO.output(realpin, GPIO.HIGH)
    except :
       return 1
    return 0

def ReadGPIOConfig():
    try:
        GPIO.setwarnings(False)    
        GPIO.setmode(GPIO.BCM)    
        GPIO.setup(17, GPIO.IN)    
        state = GPIO.input(17)
    except :
        state = 1
    WriteTimeLogfile("etat :"+str(state))
    return state

def DateToSeconds(date):
    #print("date: ",date)
    try:
        year=int(date[0:4],10)
    except :
        year=2020    
    try:
        month=int(date[5:7],10)
    except :
        month=1        
    try:
        day=int(date[8:10],10)
    except :
        day=1            
    try:
        hour=int(date[11:13],10)
    except :
        hour=0                
    try:
        mins=int(date[14:16],10)
    except :
        mins=0                    
    try:
        secs=int(date[17:19],10)
    except :
        secs=0
    #print("year:",year,"month:",month,"day:",day,"hour:",hour,"mins:",mins,"secs:",secs)
    seconds=secs+mins*60+hour*3600+day*3600*24+month*30*24*3600+year*365*30*24*3600
    #print("seconds:",seconds)
    return seconds
def SecondsToDate(seconds):
    try :
        year=str(seconds//(365*30*24*3600))
        reste=seconds%(365*30*24*3600)
        month=str(reste//(30*24*3600)).zfill(2)
        reste=reste%(30*24*3600)
        day=str(reste//(24*3600)).zfill(2)
        reste=reste%(24*3600)
        hour=str(reste//(3600)).zfill(2)
        reste=reste%(3600)
        mins=str(reste//(60)).zfill(2)
        secs=str(reste%(60)).zfill(2)
    except :
        year="2021"
        month="01"
        day="01"
        hour="00"
        mins="00"
        secs="00"
    
    try :
        #print("year:",year,"month:",month,"day:",day,"hour:",hour,"mins:",mins,"secs:",secs)    
        date=year+"-"+month+"-"+day+"T"+hour+":"+mins+":"+secs+"Z"
        #print("date:",date)
    except :
        date="2021-01-01T00:00:00Z"
    return date

def GetCurrentDate():
    try:
        now = datetime.datetime.utcnow()
        Time=str(now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    except :
        Time="2021-01-01T00:00:00Z"
    return Time
def CalculNextStartDate(StartDate,Period,CurrentDate):
    try:
        StartTime=DateToSeconds(StartDate)
        CurrentTime=DateToSeconds(CurrentDate)
        NextTime=StartTime
        now=GetCurrentDate()
        nowTime=DateToSeconds(now)+600
        print(CurrentTime,nowTime)
        while(NextTime<CurrentTime or NextTime<nowTime):
            NextTime=NextTime+Period
        print(NextTime)
        NextDate=SecondsToDate(NextTime)
    except:
        NextDate="2022-01-01T00:00:00Z"
    return NextDate

def WriteStartDateConfig(NextStartDate,NextStartseconds):        
    data = {
        "NextStartDate1" : NextStartDate[0],
        "NextStartDate2" : NextStartDate[1],
        "NextStartDate3" : NextStartDate[2],
        "NextTime1" : NextStartseconds[0],
        "NextTime2" : NextStartseconds[1],
        "NextTime3" : NextStartseconds[2],              
        }
    try :        
        json_object = json.dumps(data, indent = len(data))
        fullpath="/home/pi/Scanorhize/ConfigFile/"+"NextStartDate.json"
        
        with open(fullpath, "w") as outfile: 
            outfile.write(json_object)
    finally:
        return 0
def ReadStartDateConfig():
    NextStartseconds=[0,0,0]
    NextStartDate=["2021-01-14T11:05:00Z","2021-01-15T11:05:00Z","2021-01-16T11:05:00Z"]
    fullpath="/home/pi/Scanorhize/ConfigFile/"+"NextStartDate.json"
    try:        
        with open(fullpath, "r") as openfile:  
            data = json.load(openfile)
    except :
        WriteTimeLogfile("No file:",fullpath)
       
    else:           
        NextStartDate[0] = data["NextStartDate1"]
        NextStartDate[1] = data["NextStartDate2"]
        NextStartDate[2] = data["NextStartDate3"]
        NextStartseconds[0] = data["NextTime1"]
        NextStartseconds[1] = data["NextTime2"]
        NextStartseconds[2] = data["NextTime3"]      
        
    finally:        
        return NextStartDate,NextStartseconds

def CopyLog():
    #copy log folder to USB           
    USBPath="/media/pi/Image/"    
    LogPath="/home/pi/Scanorhize/Log"
    cmd="sudo cp -r "+LogPath+" "+USBPath
    #print(cmd)
    result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
    #print(result.returncode,result.stdout,result.stderr)
    

