#!/bin/bash



systemctl restart systemd-timesyncd.service &
sleep 5
. /home/pi/wittypi/utilities.sh && system_to_rtc
timedatectl
exit

#sudo /etc/init.d/ntp stop
#sudo ntpd -q -g
#sudo /etc/init.d/ntp start

