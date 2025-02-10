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

def DateToSeconds(date: str):
    """Return the number of seconds between the Epoch and date

    Args:
        date (str): date to convert in seconds

    Returns:
        int: number of seconds
    """
    print("date: ", date)
    try:
        date_obj = datetime.strptime(date, JAVA_FORMAT)
        date_obj = date_obj.replace(tzinfo=timezone.utc)
        seconds = int(date_obj.timestamp())
    except ValueError:
        seconds = 1732116623 # 2024-11-20
    return seconds

def SecondsToDate(seconds: int):
    try :
        date_obj = datetime.fromtimestamp(seconds, tz=timezone.utc)
        date= date_obj.strftime(JAVA_FORMAT)
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
        Time=str(datetime.now(timezone.utc).strftime(JAVA_FORMAT))
    except ValueError:
        Time=DEFAULT_DATE_TIME
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
    except ValueError:
        NextDate=DEFAULT_DATE_TIME
    return NextDate

if __name__ == "__main__":
    local_tz = time.tzname
    date_now = datetime.now(timezone.utc)
    print(date_now, date_now.tzinfo)
    date_new = GetCurrentDate()
    nb_seconds = DateToSeconds(date_new)
    print(DateToSeconds(date_new))
    print(SecondsToDate(nb_seconds))
