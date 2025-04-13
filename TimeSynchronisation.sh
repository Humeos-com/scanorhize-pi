#!/bin/bash

# check if sudo is used
if [ "$(id -u)" != 0 ]; then
  echo 'Sorry, you need to run this script with sudo'
  exit 1
fi

systemctl restart systemd-timesyncd.service &
sleep 5
. /home/pi/wittypi/utilities.sh && system_to_rtc
timedatectl
exit 0

