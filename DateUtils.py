#!/usr/bin/env python3
"""
Miscellaneous dates functions
"""

import datetime
from datetime import datetime
from datetime import timezone
import time

from ConfigApp import getLogger

# Java Zoned Timestamp, with TZ=UTC
JAVA_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_DATE_TIME = "2025-11-30T00:00:00Z"
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
        # Ensure integer seconds and guard against platform range issues
        date_obj = datetime.fromtimestamp(int(seconds), tz=timezone.utc)
        date = date_obj.strftime(JAVA_FORMAT)
    except (OverflowError, OSError, ValueError, TypeError) as e:
        getLogger().warning("SecondsToDate overflow/invalid seconds=%s: %s", seconds, e)
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


def ValidateDate(date: str):
    """
    Validate if a date string matches the JAVA_FORMAT format

    Args:
        date (str): date string to validate in JAVA_FORMAT format

    Returns:
        bool: True if date is valid, False otherwise
    """
    try:
        datetime.strptime(date, JAVA_FORMAT)
        return True
    except ValueError:
        return False


def CalculNextStartDate(DateOrigin: str, PeriodeS: int, DateStart: str):
    """Calculate the next start date for a scanner based on its configuration.
    On prend la date d'origine et on compte le nombre de périodes
    qui ont été parcourues depuis cette date.
    On ajoute une période et on obtient la date du prochain déclenchement.

    Args:
        DateOrigin (str): Initial start date in JAVA_FORMAT
        PeriodeS (int): Period in seconds between scans
        DateStart (str): Current date in JAVA_FORMAT

    Returns:
        tuple: (next_date_str, next_date_seconds)
    """
    try:
        # Convert dates to seconds
        origin_seconds = DateToSeconds(DateOrigin)
        current_seconds = DateToSeconds(DateStart)

        # Calculate the number of periods that have passed
        periods_passed = (current_seconds - origin_seconds) // PeriodeS

        # Calculate the next start date
        next_date_seconds = origin_seconds + ((periods_passed + 1) * PeriodeS)
        next_date_str = SecondsToDate(next_date_seconds)

        return next_date_str, next_date_seconds
    except (ValueError, TypeError) as e:
        getLogger().error("Error calculating next start date: %s", e)
        return DateStart, DateToSeconds(DateStart)


if __name__ == "__main__":
    local_tz = time.tzname
    date_now = datetime.now(timezone.utc)
    print(date_now, date_now.tzinfo)
    date_new = GetCurrentDate()
    nb_seconds = DateToSeconds(date_new)
    print(DateToSeconds(date_new))
    print(SecondsToDate(nb_seconds))
    print(ConvertDateToWitty(date_new))
    print(CalculNextStartDate("2025-01-01T00:00:00Z", 3600, date_new))
