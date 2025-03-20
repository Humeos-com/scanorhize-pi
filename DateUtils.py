"""
Miscellaneous dates functions
"""

import datetime
from datetime import datetime
from datetime import timezone
import time

# Java Zoned Timestamp, with TZ=UTC
JAVA_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_DATE_TIME = "2024-11-01T00:00:00Z"
DEFAULT_SECONDS = 1742310000  # 2025-03-18T15:00:00Z


def DateToSeconds(date: str):
    """Return the number of seconds between the Epoch and date

    Args:
        date (str): date to convert in seconds

    Returns:
        int: number of seconds
    """
    try:
        date_obj = datetime.strptime(date, JAVA_FORMAT)
        date_obj = date_obj.replace(tzinfo=timezone.utc)
        seconds = int(date_obj.timestamp())
    except ValueError:
        seconds = DEFAULT_SECONDS
    return seconds


def SecondsToDate(seconds: int):
    try:
        date_obj = datetime.fromtimestamp(seconds, tz=timezone.utc)
        date = date_obj.strftime(JAVA_FORMAT)
    except ValueError:
        date = DEFAULT_DATE_TIME
    return date


def GetCurrentDate():
    """
    Get current UTC TimeStamp string in JAVA Format

    Returns:
        str: current UTC TimeStamp
    """
    try:
        Time = str(datetime.now(timezone.utc).strftime(JAVA_FORMAT))
    except ValueError:
        Time = DEFAULT_DATE_TIME
    return Time


def CalculNextStartDate(StartDate: str, Period: int, CurrentDate: str):
    """Calcule la prochaine date de début de campagne au format JAVA UTC
    Compte combien de fois la période s'est écoulée depuis la date de début
    et retourne la prochaine date de début de campagne

    Args:
        StartDate (str): en JAVA UTC
        Period (int): en secondes
        CurrentDate (str): en JAVA UTC

    Returns:
        string: la prochaine date de début de campagne en JAVA UTC
        int: la prochaine date de début de campagne en secondes
    """
    try:
        Periodi = int(Period)
        StartTime = DateToSeconds(StartDate)
        CurrentTime = DateToSeconds(CurrentDate)
        NextTime = StartTime
        now = GetCurrentDate()
        nowTime = DateToSeconds(now) + 180
        while NextTime < CurrentTime or NextTime < nowTime:
            NextTime = NextTime + Periodi
        NextDate = SecondsToDate(NextTime)
    except ValueError:
        NextDate = DEFAULT_DATE_TIME
        NextTime = DEFAULT_SECONDS
    return NextDate, NextTime


def ConvertDateToWitty(date: str):
    """
    Convert date from JAVA to WittyPy format

    Args:
        date (str): date in JAVA format

    Returns:
        str: date in WittyPy format "DD HH MM SS"
    """
    try:
        date_obj = datetime.strptime(date, JAVA_FORMAT)
        date = date_obj.strftime("%d %H %M %S")
    except ValueError:
        date = "01 06 25 00"
    return date


if __name__ == "__main__":
    local_tz = time.tzname
    date_now = datetime.now(timezone.utc)
    print(date_now, date_now.tzinfo)
    date_new = GetCurrentDate()
    nb_seconds = DateToSeconds(date_new)
    print(DateToSeconds(date_new))
    print(SecondsToDate(nb_seconds))
    print(ConvertDateToWitty(date_new))
    print(CalculNextStartDate(DEFAULT_DATE_TIME, "3600", date_new))
