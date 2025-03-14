"""
Archive les fichiers au format JP2
"""

from subprocess import run
import os
from Miscellaneous import WriteTimeLogfile
from OSUtils import is_raspberry_pi


FolderImage = "/home/pi/Documents"


def CreateFolderImage(Name, i_scan):
    """Create folder on USB device, on failure use /home/pi/Documents

    Args:
        Name (str): Folder name
        i_scan (str): Scanner name

    Returns:
        str: the right place for images
    """
    global FolderImage
    BackupFolder = "/home/pi/Documents"
    try:
        USB = USBSpace()
        USBfolder = USB[2]
        scannum = "Scanner" + str(i_scan + 1)
        FolderImage = USBfolder + "/" + Name + "/" + scannum + "/"
        data = "Folder save: " + FolderImage
        if not os.path.exists(FolderImage):
            os.makedirs(FolderImage)
    except OSError as err:
        FolderImage = BackupFolder
        WriteTimeLogfile("CreateFolder Error: " + err + "set to backup")
        data = "Folder save: " + FolderImage

    WriteTimeLogfile(data)
    return FolderImage


def USBDrive():
    USBfolder = "/media/pi/"
    BackupFolder = "/home/pi/Documents"
    try:
        dirlist = os.listdir(USBfolder)
        print(dirlist)
        mediafolders = len(dirlist)
        print("sizedirlist : ", mediafolders)
        if mediafolders > 0:
            MountFolder = USBfolder + dirlist[0]
        else:
            MountFolder = BackupFolder
    except OSError:
        MountFolder = BackupFolder
    return MountFolder


def CopyImageToUSB(Scanner, FolderImage_):
    try:
        date = Scanner.LastImgTime
        fileName = date.replace(":", "-")
        imagejpg2000 = fileName + ".jp2"
        jp2Path = FolderImage_ + imagejpg2000
        print(jp2Path)
        cmd = "sudo cp " + Scanner.LastImgFile + " " + jp2Path
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=False
        )
        if result.returncode == 0:
            return 0
        WriteTimeLogfile(
            str(result.returncode) + str(result.stdout) + str(result.stderr)
        )
        return result.returncode
    except OSError:
        return 1


def CreateTempImage(Scanner):
    try:
        imagepath = "static/"
        Date = (Scanner.LastImgTime).replace(":", "-")
        Imagejp2000Path = Scanner.LastImgFile
        jp2Path = imagepath + Date + ".jp2"
        # print(jp2Path)
        cmd = "sudo cp " + Imagejp2000Path + " " + jp2Path
        print(cmd)
        result = run(
            cmd, capture_output=True, universal_newlines=True, shell=True, check=False
        )
        if result.returncode == 0:
            return jp2Path
        WriteTimeLogfile(
            str(result.returncode) + str(result.stdout) + str(result.stderr)
        )
        return jp2Path
    except OSError:
        jp2Path = "static/error.jp2"
        return jp2Path


def RemoveTempImage(Image):
    cmd = "/bin/rm -f " + Image
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    if result.returncode == 0:
        return 0
    WriteTimeLogfile(str(result.returncode) + str(result.stdout) + str(result.stderr))
    return result.returncode


def USBSpace():
    USBfolder = "/media/pi/"
    BackupFolder = "/home/pi/Documents"
    if not is_raspberry_pi():
        return 4096, 98, USBfolder

    cmd = "df -hm"
    result = run(
        cmd, capture_output=True, universal_newlines=True, shell=True, check=False
    )
    # print(result.stdout, type(result.stdout))
    try:
        x = (result.stdout).split("\n")
        for line in x:
            res = USBfolder in line
            if res:
                USBline = line
                break
        print(USBline)
        x = (USBline).split()

        FreeSpace = x[3]
        FreePercent = x[4]
        MountFolder = x[5]
    except OSError:
        FreeSpace = 0
        FreePercent = 0
        MountFolder = BackupFolder
        WriteTimeLogfile(
            str(result.returncode) + str(result.stdout) + str(result.stderr)
        )
    print(FreeSpace, FreePercent, MountFolder)
    return FreeSpace, FreePercent, MountFolder
