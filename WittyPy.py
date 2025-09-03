#!/usr/bin/env python3
"""
Gestionnaire du scheduleur RTC de la carte WittyPi.
On utilise les commandes Shell fournies par WittyPi.
Ca fonctionne quelque soit la version de la carte WittyPi.
"""

from subprocess import run
from datetime import datetime, timedelta

from OSUtils import is_raspberry_pi
from DateUtils import ConvertDateToWitty
from ConfigApp import getLogger

path = "/home/pi/wittypi/"


def ReadWittyFunction(function):
    source = "source" + " " + path + "utilities.sh && " + function
    print(source)
    if not is_raspberry_pi():
        return 0
    result = run(["sudo", "bash", "-c", source], capture_output=True, check=False)
    print(result.stdout)
    return result.stdout


def WriteWittyFunction(function, arg):
    source = "source" + " " + path + "utilities.sh && " + function + " " + arg
    print(source)
    if not is_raspberry_pi():
        return 0
    result = run(["sudo", "bash", "-c", source], capture_output=True, check=False)
    print(result.stdout)
    return result.stdout


def ReadNextStartDate():
    tempstringbyte = ReadWittyFunction("get_startup_time")
    tempstring = str(tempstringbyte)
    res1 = tempstring.split("'")
    res2 = res1[1].split("\\")
    date = res2[0]
    try:
        day = int(date[0:2], 10)
    except ValueError:
        day = 1
    try:
        hour = int(date[3:5], 10)
    except ValueError:
        hour = 0
    try:
        mins = int(date[6:8], 10)
    except ValueError:
        mins = 0
    try:
        secs = int(date[9:11], 10)
    except ValueError:
        secs = 0
    # print("day:",day,"hour:",hour,"mins:",mins,"secs:",secs)
    # print(date)
    return (date, day, hour, mins, secs)


def SetNextStartDate(date):  # date en UTC!!
    """Set the next startup time for the WittyPi.
    If the parsing of the date fails, the next day is used as default.

    Args:
        date (str): Date string in format "YYYY-MM-DDTHH:mm:ssZ"

    Returns:
        int: Result of WriteWittyFunction call, or 0 if not on Raspberry Pi
    """

    if not is_raspberry_pi():
        return 0
    # Get current date plus one day for defaults
    tomorrow = datetime.utcnow() + timedelta(days=1)
    defaults = {
        "year": tomorrow.year,
        "month": tomorrow.month,
        "day": tomorrow.day,
        "hour": tomorrow.hour,
        "mins": tomorrow.minute,
        "secs": tomorrow.second,
    }

    # Parse date components with error handling
    try:
        # Extract components using string slicing
        components = {
            "year": int(date[0:4]),
            "month": int(date[5:7]),
            "day": int(date[8:10]),
            "hour": int(date[11:13]),
            "mins": int(date[14:16]),
            "secs": int(date[17:19]),
        }
    except (ValueError, IndexError) as e:
        # Use tomorrow's date if parsing fails
        components = defaults
        getLogger().error("Error parsing date: %s", e)

    # Format the time string
    arg = f"{components['day']:02d} {components['hour']:02d} {components['mins']:02d} {components['secs']:02d}"

    # Only proceed if running on Raspberry Pi

    return WriteWittyFunction("set_startup_time", arg)


def setNextShutdownDate(date: str):
    """_summary_

    Args:
        date (str): Date in JAVA format

    Returns:
        result: Date in WittyPi format "DD HH MM SS"
    """

    datew = ConvertDateToWitty(date)
    if not is_raspberry_pi():
        return 0
    return WriteWittyFunction("set_shutdown_time", datew)


def doShutdown():
    return ReadWittyFunction("do_shutdown")
