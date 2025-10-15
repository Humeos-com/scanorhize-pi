#!/usr/bin/env python3
"""
Archive les fichiers au format JP2
"""

import os
from os import path

# import sys
import shutil
from OSUtils import is_raspberry_pi
from ConfigApp import getLogger, getUsbDir

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


def CopyImageToUSB(Scanner, FolderImage_):
    """copie l'image et le fichier JSON sur la clé USB"""
    try:
        date = Scanner.LastImgTime
        fileName = date.replace(":", "-")
        jp2Path = path.join(FolderImage_, f"image_{fileName}.jp2")
        jp2JSONPath = path.join(FolderImage_, f"image_{fileName}.json")
        thumbPath = path.join(FolderImage_, f"image_{fileName}_thumb.jpg")

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

        # Copy thumbnail if it exists
        if Scanner.LastThumbFile and os.path.exists(Scanner.LastThumbFile):
            getLogger().warning("Copy %s to %s", Scanner.LastThumbFile, thumbPath)
            shutil.copy2(Scanner.LastThumbFile, thumbPath)
        else:
            getLogger().warning("No thumbnail to copy")

        return 0

    except (IOError, OSError) as err:
        getLogger().error("CopyImageToUSB: Error: %s", err)
        return 1


def USBSpace():
    """Get the USB space

    Returns:
        int: free space in MB
        int: free space in percentage
        str: USB directory
    """
    USB_DIR = getUsbDir()
    if not is_raspberry_pi():
        return 4096, 100, USB_DIR

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
