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
    sleep 30
    WIRED_CONNECTION=$(nmcli -t --field UUID,DEVICE  connection show --active | grep "eth1")
    if [ "bidon" = "bidon$WIRED_CONNECTION" ]
    then
        echo "Wired connection not found."
        continue;
    fi
    UUID=$(echo $WIRED_CONNECTION | cut -d':' -f 1)
    nmcli connection down "$UUID"
    echo "Connection $WIRED_CONNECTION shut down"
    continue;
done

