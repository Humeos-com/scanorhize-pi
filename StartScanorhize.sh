#!/bin/bash

cd /home/pi/Scanorhize
DATE=$(date '+%Y-%m-%d_%H%M%S')

if [ -e DEBUG ]
then
    echo "DEBUG mode: on mesure le courant."
    # python3 WittyPython.py > Log/courant_$DATE.log &
fi
python3 ScanorhizeStart.py >> Log/ScanorhizeStart.log 2>&1 &

