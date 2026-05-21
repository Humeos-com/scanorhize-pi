#!/bin/bash

# config
INTERFACE_WIFI="wlan0"
INTERFACE_LTE="wwan0"
TARGET="google.com"
MODEM_PORT="/dev/ttyUSB2" #to be tested depending on the modem used
QMI_DEV="/dev/cdc-wdm0"

TEST_SIZE_MB=5  #can be tuned ; used for both downloading and uploading tests
TEST_SIZE_BYTES=$((TEST_SIZE_MB * 1048576))

DOWNLOAD_URL="https://speed.cloudflare.com/__down?bytes=$TEST_SIZE_BYTES" 
UPLOAD_URL="https://speed.cloudflare.com/__up"


if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] Please call this script with sudo to monitor radio signal quality"
fi



#1 checking if the hub is an AP or a client ; testing radio signal quality if AP
WIFI_MODE=$(iw dev "$INTERFACE_WIFI" info 2>/dev/null | grep "type" | awk '{print $2}')

if [ "$WIFI_MODE" = "managed" ]; then
    echo "[INFO] Hub is a client"
    INTERFACE_TO_TEST="$INTERFACE_WIFI"
    
elif [ "$WIFI_MODE" = "AP" ]; then
    echo "[INFO] Hub is an AP"
    INTERFACE_TO_TEST="$INTERFACE_LTE"

#radio qlty test ##############
if [ -e "$QMI_DEV" ]; then
    echo "[INFO] Interrogating modem via QMI..."
    
    #trying 3 times with 5s timeout
    QMI_OUT=""
    for i in {1..3}; do

        QMI_OUT=$(timeout 10 qmicli -p -d "$QMI_DEV" --nas-get-signal-info 2>/dev/null)
        if echo "$QMI_OUT" | grep -q "RSRP"; then
            break
        fi
        echo "[RETRY] Modem busy or no answer (attempt $i/3), retrying..."
        sleep 1
    done

    if echo "$QMI_OUT" | grep -q "RSRP"; then
        #extracting signal quality from qmi response
        RSRP_DBM=$(echo "$QMI_OUT" | grep "RSRP:" | awk '{print $2}' | tr -d 'dBm')
        RSRQ_DB=$(echo "$QMI_OUT" | grep "RSRQ:" | awk '{print $2}' | tr -d 'dB')
        SINR_DB=$(echo "$QMI_OUT" | grep -E "S(I)?NR" | cut -d"'" -f2 | awk '{print $1}')

        echo "[INFO] RSRP (Power): exc >-80 | good -80 to -90 | avg -90 to -100 | weak <-105"
        echo -e "[INFO] RSRP: ${RSRP_DBM} dBm\n" 
        echo "[INFO] RSRQ (Stability): exc >-10 | good -10 to -15 | avg -15 to -20 | bad <-20"
        echo -e "[INFO] RSRQ: ${RSRQ_DB} dB\n"
        echo "[INFO] SINR (Purity): exc >20 | good 13 to 20 | avg 0 to 12 | critical <0"
        echo -e "[INFO] SINR: ${SINR_DB} dB\n"

    else
        echo "[ERROR] Failed to get radio quality values via QMI after several retries."
    fi
else
    echo "[ERROR] QMI device $QMI_DEV not found."
fi
################################

else
    echo "[ERROR] Wifi state unknown $WIFI_MODE"
    exit 1
fi

#2 DNS test avec dig (plus robuste pour le LTE/WWAN)
DNS_OK=false

echo "[INFO] Testing DNS resolution on $INTERFACE_TO_TEST..."

    # 1st try : using default system DNS
REPLY=$(dig +short +timeout=5 +tries=3 "$TARGET")

if [ -n "$REPLY" ]; then
    DNS_OK=true
    # 2nd try : using google's DNS to spot local config issue
else
    REPLY_ALT=$(dig +short +timeout=5 +tries=3 @8.8.8.8 "$TARGET")
    if [ -n "$REPLY_ALT" ]; then
        echo "[WARN] System DNS failed, but Google DNS worked. Local config issue."
        DNS_OK=true
    fi
fi

if [ "$DNS_OK" = false ]; then
    echo "[ERROR] DNS fail on $INTERFACE_TO_TEST"
    exit 1
else
    echo "[INFO] DNS OK on $INTERFACE_TO_TEST"
fi

#3 latency, jitter, packet loss
PING_RAW=$(ping -c 5 -i 0.5 -q -I "$INTERFACE_TO_TEST" "8.8.8.8" 2>/dev/null)

if [ -n "$PING_RAW" ]; then
    #getting delay values   
    STATS=$(echo "$PING_RAW" | grep "rtt" | cut -d' ' -f4)
    MIN=$(echo "$STATS" | cut -d'/' -f1)
    AVG=$(echo "$STATS" | cut -d'/' -f2)
    MAX=$(echo "$STATS" | cut -d'/' -f3)
    
    # packet loss
    LOSS=$(echo "$PING_RAW" | grep -o "[0-9]*%" | head -1 | tr -d '%')
    
    #jitter calculation
    if [ -n "$MAX" ] && [ -n "$MIN" ]; then
        JITTER=$(awk "BEGIN {printf \"%.2f\", $MAX - $MIN}")
    else
        JITTER="0.00"
    fi

    echo "[INFO] Ping: ${AVG}ms (Min:${MIN} / Max:${MAX})"
    echo "[INFO] Jitter: ${JITTER}ms"
    echo "[INFO] Packet Loss: ${LOSS}%"

    # MTU test
    if ping -c 1 -M do -s 1472 -I "$INTERFACE_TO_TEST" "$TARGET" >/dev/null 2>&1; then
        echo "[INFO] MTU: 1500 OK (No fragmentation)"
    else
        echo "[WARN] MTU: 1500 Failed (Fragmentation detected)"
    fi
else
    echo "[ERROR] Ping: Cannot reach host"
    exit 1
fi

#4 speed test by downloading/uploading 1MB file over 10s max
echo "[INFO] Testing network speed..."
DOWNLOAD_SPEED_BYTES=$(curl -4 -s -o /dev/null --interface "$INTERFACE_TO_TEST" --user-agent "Mozilla/5.0" --max-time 15 -w "%{speed_download}" "$DOWNLOAD_URL")
UPLOAD_SPEED_BYTES=$(head -c "$TEST_SIZE_BYTES" /dev/urandom | curl -4 -s -o /dev/null --interface "$INTERFACE_TO_TEST" --user-agent "Mozilla/5.0" --max-time 40 -w "%{speed_upload}" --data-binary @- "$UPLOAD_URL")
    #speed calculation in MB/s

DOWNLOAD_MB_S=$(awk "BEGIN {printf \"%.2f\", $DOWNLOAD_SPEED_BYTES / 1048576}")
UPLOAD_MB_S=$(awk "BEGIN {printf \"%.2f\", $UPLOAD_SPEED_BYTES / 1048576}")

echo "[INFO] Downloading speed on $INTERFACE_TO_TEST : $DOWNLOAD_MB_S MB/s"
echo "[INFO] Upload speed on $INTERFACE_TO_TEST : $UPLOAD_MB_S MB/s"