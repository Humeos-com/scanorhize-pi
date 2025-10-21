#!/bin/sh

# Script qui désactive la connexion directe par la clé 4G
# afin de n'utiliser que le Wifi Scanorhize, et ainsi
# permettre l'accès à l'interface Web du Hub sur l'IP 192.168.1.42

# check if sudo is used
if [ "$(id -u)" != 0 ]; then
  echo 'Sorry, you need to run this script with sudo'
  exit 1
fi

while [ true ]
do
    sleep 10
    # usb0 sur les Raspberry Pi 4
    # eth1 sur les Raspberry Pi 5
    WIRED_CONNECTION=$(/usr/bin/nmcli -t --field UUID,DEVICE  connection show --active | grep "eth1\|usb0")
    if [ "bidon" = "bidon$WIRED_CONNECTION" ]
    then
        echo "$(date '+%F %T') - Wired connection not found."
        continue;
    fi
    UUID=$(echo $WIRED_CONNECTION | cut -d':' -f 1)
    /usr/bin/nmcli connection down "$UUID"
    echo "$(date '+%F %T') - Connection $WIRED_CONNECTION shut down"
    continue;
done

