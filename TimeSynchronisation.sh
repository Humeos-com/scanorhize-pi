

sudo systemctl restart systemd-timesyncd.service &
sleep 5
cd /home/pi/wittypi && . utilities.sh && system_to_rtc
timedatectl

#sudo /etc/init.d/ntp stop
#sudo ntpd -q -g
#sudo /etc/init.d/ntp start

