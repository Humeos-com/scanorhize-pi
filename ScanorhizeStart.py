"""Lance le scanner et programme le prochain réveil"""

from subprocess import call
from WittyPy import SetNextStartDate
from Miscellaneous import InitGPIO, TurnPin_On, ReadGPIOConfig, WriteTimeLogfile
from DateUtils import GetCurrentDate, SecondsToDate, DateToSeconds

WriteTimeLogfile("ScanorhizeStart.py")

res = InitGPIO()
if res != 0:
    WriteTimeLogfile("InitGPIOError")
res = TurnPin_On(3, 0)
if res != 0:
    WriteTimeLogfile("TurnPinOnError")

config = ReadGPIOConfig()

# connexion réseau en parralèle pour optimiser le temps
# res=0
# iteration=0
# while res==0 and iteration<12:
# res=pingAPI("www.google.com")
# if res==0:
#   cmd="sudo ifconfig wlan0 down"
#  WriteTimeLogfile(cmd)
# subprocess.call(cmd,shell=True)
# cmd="sudo ifconfig wlan0 up"
# WriteTimeLogfile(cmd)
# subprocess.call(cmd,shell=True)
# sleep(20)
# WriteTimeLogfile(str(res)+" "+str(iteration))
# iteration=iteration+1


if config == 0:
    # En mode config
    cmd = "sudo python3 /home/pi/Scanorhize/Scanorhize.py &"
    WriteTimeLogfile(cmd)
    call(cmd, shell=True)
else:
    DateStart = GetCurrentDate()
    CurrentDateinS = DateToSeconds(DateStart)
    NextDate = SecondsToDate(CurrentDateinS + (3600 * 1))  # demarrage toutes les 1h
    StopTime = SecondsToDate(
        CurrentDateinS + (60 * 20)
    )  # arret au bout de 20min par sécurité en cas d'erreur
    WriteTimeLogfile("Set NextDate: " + NextDate)
    SetNextStartDate(NextDate)
    # WriteTimeLogfile("Set StopTime: "+StopTime)
    cmd = "sudo python3 /home/pi/Scanorhize/ScanorhizeProcess.py &"
    WriteTimeLogfile(cmd)
    call(cmd, shell=True)

# cmd="midori -e Fullscreen"
# print(cmd)
# subprocess.call(cmd,shell=True)
