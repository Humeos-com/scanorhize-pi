"""
Archive les fichiers au format JP2
"""

import os
from os import path
# import sys
import shutil
from Miscellaneous import WriteTimeLogfile
from OSUtils import is_raspberry_pi

# Define base folders for different platforms
if is_raspberry_pi():
    BASE_DIR = "/home/pi"
    USB_DIR = "/media/pi"
else:
    # For Windows/macOS development
    BASE_DIR = path.join(path.dirname(path.dirname(__file__)))
    USB_DIR = path.join(BASE_DIR, "media")

# Define derived paths using os.path.join
DOCUMENTS_DIR = path.join(BASE_DIR, "Documents")
FOLDER_IMAGE = DOCUMENTS_DIR  # Default folder for images


def CreateFolderImage(Name, i_scan):
    """Create folder on USB device, on failure use /home/pi/Documents

    Args:
        Name (str): Folder name
        i_scan (str): Scanner name

    Returns:
        str: the right place for images
    """
    try:
        USB = USBSpace()
        USBfolder = USB[2]
        scannum = "Scanner" + str(i_scan + 1)
        FolderImage = USBfolder + "/" + Name + "/" + scannum + "/"
        data = "Folder save: " + FolderImage
        if not os.path.exists(FolderImage):
            os.makedirs(FolderImage)
    except OSError as err:
        FolderImage = FOLDER_IMAGE
        WriteTimeLogfile("CreateFolder Error: " + err + "set to backup")
        data = "Folder save: " + FOLDER_IMAGE

    WriteTimeLogfile(data)
    return FolderImage


def CopyImageToUSB(Scanner, FolderImage_):
    try:
        date = Scanner.LastImgTime
        fileName = date.replace(":", "-")
        imagejpg2000 = fileName + ".jp2"
        jp2Path = FolderImage_ + imagejpg2000
        print(jp2Path)
        # Check if source file exists
        if not os.path.exists(Scanner.LastImgFile):
            WriteTimeLogfile(f"Source file not found: {Scanner.LastImgFile}")
            return 1
        # Use shutil.copy2 instead of shell command
        shutil.copy2(Scanner.LastImgFile, jp2Path)
        return 0

    except (IOError, OSError) as err:
        WriteTimeLogfile(f"CopyImageToUSB: Error: {str(err)}")
        return 1

def CreateTempImage(Scanner):
    try:
        imagepath = "static/"
        Date = (Scanner.LastImgTime).replace(":", "-")
        Imagejp2000Path = Scanner.LastImgFile
        jp2Path = imagepath + Date + ".jp2"

        # Check if source file exists
        if not os.path.exists(Imagejp2000Path):
            WriteTimeLogfile(f"Source file not found: {Imagejp2000Path}")
            return "static/error.jp2"

        # Use shutil.copy2 instead of shell command
        shutil.copy2(Imagejp2000Path, jp2Path)
        return jp2Path

    except (IOError, OSError) as err:
        print(f"File copy error: {err}")
        WriteTimeLogfile(f"Error in CreateTempImage: {str(err)}")
        return "static/error.jp2"


def RemoveTempImage(Image):
    try:
        os.remove(Image)
        return 0
    except OSError as err:
        WriteTimeLogfile(f"Error removing {Image}: {err}")
        return 1


def USBSpace():
    if not is_raspberry_pi():
        return 4096, 98, USB_DIR

    try:
        stat = os.statvfs(USB_DIR)

        # Calculate free space in MB
        free_space = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)

        # Calculate percentage free
        total_space = (stat.f_blocks * stat.f_frsize) / (1024 * 1024)
        free_percent = (free_space / total_space) * 100

        return int(free_space), int(free_percent), USB_DIR

    except OSError as err:
        WriteTimeLogfile(f"Error getting disk space: {err}")
        return 0, 0, FOLDER_IMAGE
