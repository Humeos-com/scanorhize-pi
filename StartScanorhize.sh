#!/bin/bash

cd /home/pi/Scanorhize
DATE=$(date '+%Y-%m-%d:%H:%M:%S')
python3 WittyPython.py > Log/courant_$DATE.log &
sudo python3 ScanorhizeStart.py &

