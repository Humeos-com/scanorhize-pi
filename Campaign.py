import subprocess
from subprocess import PIPE, run
import datetime
import json
import os
from Miscellious import *

def CreateFolderImage(Name, i_scan):
    BackupFolder="/home/pi/Documents"
    global FolderImage
    try:
        USB=USBSpace()
        USBfolder=USB[2]       
        scannum="Scanner"+str(i_scan+1)
        FolderImage=USBfolder+"/"+Name+"/"+scannum+"/"
        data="Folder save: "+FolderImage
        if not os.path.exists(FolderImage):
            os.makedirs(FolderImage)            
    except :
        FolderImage=BackupFolder
        WriteTimeLogfile("CreateFolder Error :set to backup")
        data="Folder save: "+FolderImage
    
    WriteTimeLogfile(data)    
    return FolderImage

def USBDrive():
    USBfolder="/media/pi/"
    BackupFolder="/home/pi/Documents"
    try :
        dirlist = os.listdir(USBfolder)
        print(dirlist)
        mediafolders=len(dirlist)
        print("sizedirlist : ",mediafolders)
        if mediafolders>0 :
            MountFolder=USBfolder+dirlist[0]
        else :
            MountFolder=BackupFolder
    except :
        MountFolder=BackupFolder
    return MountFolder

def CopyImageToUSB(Scanner, FolderImage):
    try:
        date=Scanner.LastImgTime
        fileName=date.replace(":","-")
        imagejpg2000=fileName+".jp2"    
        jp2Path=FolderImage+imagejpg2000
        #print(jp2Path)
        cmd="sudo cp "+Scanner.LastImgFile+" "+jp2Path
        result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
        if result.returncode==0 :
            return 0
        else :
            WriteTimeLogfile(str(result.returncode)+str(result.stdout)+str(result.stderr))
            return result.returncode
    except:
        return 1
def CreateTempImage(Scanner):
    try:
        imagepath = "/home/pi/Scanorhize/static/"
        Date=(Scanner.LastImgTime).replace(":","-")
        Imagejp2000Path=Scanner.LastImgFile      
        jp2Path=imagepath+Date+".jp2"    
        #print(jp2Path)
        cmd="sudo cp "+Imagejp2000Path+" "+jp2Path
        result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
        if result.returncode==0 :
            return jp2Path
        else :
            WriteTimeLogfile(str(result.returncode)+str(result.stdout)+str(result.stderr))
        return jp2Path
    except:
        jp2Path="/home/pi/Scanorhize/static/error.jp2"
        return jp2Path
def RemoveTempImage(Image):    
    cmd="rm "+Image
    result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
    if result.returncode==0 :
        return 0
    else :
        WriteTimeLogfile(str(result.returncode)+str(result.stdout)+str(result.stderr))
    return result.returncode

def USBSpace():
    USBfolder="/media/pi/"
    BackupFolder="/home/pi/Documents"
    cmd="df -hm"
    result = run(cmd, capture_output=True, universal_newlines=True, shell=True)
    #print(result.stdout, type(result.stdout))
    try:
        x=(result.stdout).split('\n')
        for line in x :
            res=USBfolder in line
            if res :
                USBline=line
                break       
        #print(USBline)
        x=(USBline).split()
        
        FreeSpace=x[3]
        FreePercent=x[4]
        MountFolder=x[5]
    except:
        FreeSpace=0
        FreePercent=0
        MountFolder=BackupFolder
        WriteTimeLogfile(str(result.returncode)+str(result.stdout)+str(result.stderr))
    #print(FreeSpace,FreePercent,MountFolder)
    return FreeSpace, FreePercent,MountFolder

    