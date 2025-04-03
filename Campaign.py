"""
Archive les fichiers au format JP2
"""

import os
from os import path

# import sys
import shutil
from OSUtils import is_raspberry_pi
from ConfigApp import getLogger, getUsbDir, getImageDir

# Define base folders for different platforms
if is_raspberry_pi():
    BASE_DIR = "/home/pi"
else:
    # For Windows/macOS development
    BASE_DIR = path.join(path.dirname(path.dirname(__file__)))

# Define derived paths using os.path.join
DOCUMENTS_DIR = path.join(BASE_DIR, "Documents")
FOLDER_IMAGE = DOCUMENTS_DIR  # Default folder for images

def CreateFolderOnUSB(directory: str):
    """Create folder on USB device, on failure use /home/pi/Documents

    Args:
        Name (str): Folder name

    Returns:
        str: the right place for images
    """
    try:
        USBfolder = getUsbDir()
        Folder = path.join(USBfolder, directory)
        data = "Folder Image: " + Folder
        if not os.path.exists(Folder):
            os.makedirs(Folder)
    except (IOError, OSError) as err:
        Folder = FOLDER_IMAGE
        getLogger().error("CreateFolder Error: %s set to backup", err)
        data = "Folder save: " + FOLDER_IMAGE

    getLogger().warning(data)
    return Folder


def CreateFolderImage(Name, i_scan):
    """Create folder on USB device, on failure use /home/pi/Documents

    Args:
        Name (str): Folder name
        i_scan (str): Scanner name

    Returns:
        str: the right place for images
    """
    try:
        USBfolder = getUsbDir()
        scannum = "Scanner" + str(i_scan + 1)
        FolderImage = path.join(USBfolder, Name, scannum)
        data = "Folder Image: " + FolderImage
        if not os.path.exists(FolderImage):
            os.makedirs(FolderImage)
    except (IOError, OSError) as err:
        FolderImage = FOLDER_IMAGE
        getLogger().error("CreateFolder Error: %s set to backup", err)
        data = "Folder save: " + FOLDER_IMAGE

    getLogger().warning(data)
    return FolderImage


def CopyImageToUSB(Scanner, FolderImage_):
    """copie l'image et le fichier JSON sur la clé USB
    """
    try:
        date = Scanner.LastImgTime
        fileName = date.replace(":", "-")
        jp2Path = path.join(FolderImage_, f"image_{fileName}.jp2")
        jp2JSONPath = path.join(FolderImage_, f"image_{fileName}.json")
        # Check if source file exists
        if not os.path.exists(Scanner.LastImgFile):
            getLogger().error("Source file not found: %s", Scanner.LastImgFile)
            return 1
        # Create the JSON file
        if Scanner.scanDumpMeta(jp2JSONPath):
            getLogger().error("Error creating JSON file: %s", jp2JSONPath)
            return 1
        getLogger().warning("Copy %s to %s", Scanner.LastImgFile, jp2Path)
        shutil.copy2(Scanner.LastImgFile, jp2Path)
        return 0

    except (IOError, OSError) as err:
        getLogger().error("CopyImageToUSB: Error: %s", err)
        return 1


def CreateTempImage(Scanner):
    try:
        image_dir = getImageDir()
        Date = (Scanner.LastImgTime).replace(":", "-")
        Imagejp2000Path = Scanner.LastImgFile
        jp2Path = f"{path.join(image_dir, Date)}.jp2"

        # Check if source file exists
        if not os.path.exists(Imagejp2000Path):
            getLogger().error("Source file not found: %s", Imagejp2000Path)
            return path.join(image_dir, "error.jp2")

        # Use shutil.copy2 instead of shell command
        shutil.copy2(Imagejp2000Path, jp2Path)
        return jp2Path

    except (IOError, OSError) as err:
        getLogger().error("Error in CreateTempImage: %s", err)
        return path.join(image_dir, "error.jp2")


def RemoveTempImage(Image):
    try:
        os.remove(Image)
        return 0
    except (IOError, OSError) as err:
        getLogger().error("Error removing %s: %s", Image, err)
        return 1


def USBSpace():
    USB_DIR = getUsbDir()
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

    except (IOError, OSError) as err:
        getLogger().error("USBSpace: Error getting disk space: %s", err)
        return 0, 0, FOLDER_IMAGE
