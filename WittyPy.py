"""
Gestionnaire du scheduleur RTC/alimentation Witty Pi
"""

from subprocess import run

from OSUtils import is_raspberry_pi
from DateUtils import ConvertDateToWitty

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


def ReadTemp():
    tempstringbyte = ReadWittyFunction("get_temperature")
    if not is_raspberry_pi():
        return 0.0
    tempstring = str(tempstringbyte)
    res1 = tempstring.split("'")
    res2 = res1[1].split("\\")
    temp = round(float(res2[0]), 1)
    print(temp)
    return temp


def ReadCurrent():
    tempstringbyte = ReadWittyFunction("get_output_current")
    if not is_raspberry_pi():
        return 0.0
    tempstring = str(tempstringbyte)
    res1 = tempstring.split("'")
    res2 = res1[1].split("\\")
    current = float(res2[0])
    print(current)
    return current


def ReadVoltage():
    tempstringbyte = ReadWittyFunction("get_output_voltage")
    if not is_raspberry_pi():
        return 0.0
    tempstring = str(tempstringbyte)
    res1 = tempstring.split("'")
    res2 = res1[1].split("\\")
    volt = float(res2[0])
    print(volt)
    return volt


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
    print("date: ", date)
    try:
        year = int(date[0:4], 10)
    except ValueError:
        year = 2020
    try:
        month = int(date[5:7], 10)
    except ValueError:
        month = 1
    try:
        day = int(date[8:10], 10)
    except ValueError:
        day = 1
    try:
        hour = int(date[11:13], 10)
    except ValueError:
        hour = 0
    try:
        mins = int(date[14:16], 10)
    except ValueError:
        mins = 0
    try:
        secs = int(date[17:19], 10)
    except ValueError:
        secs = 0
    arg = f"{day:02d} {hour:02d} {mins:02d} {secs:02d}"
    print(
        "year:",
        year,
        "month:",
        month,
        "DD HH MM SS",
        arg,
    )
    if not is_raspberry_pi():
        return 0
    result = WriteWittyFunction("set_startup_time", arg)
    return result


def setNextShutdownDate(date: str):
    """_summary_

    Args:
        date (str): Date in JAVA format

    Returns:
        result: Date in WittyPi format "DD HH MM SS"
    """

    datew = ConvertDateToWitty(date)
    print(f"date: {date} => datew: {datew}")
    if not is_raspberry_pi():
        return 0
    return WriteWittyFunction("set_shutdown_time", datew)


def doShutdown():
    return ReadWittyFunction("do_shutdown")
