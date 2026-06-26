#!/bin/bash

##########################################################
# Humeos Multi-Scanner Sync Script to S3
#
# This script:
# 1. Discovers all scanners from JSON files in $CONFIG_DIR
# 2. Reads projectId and sampleId from each scanner JSON files
# 3. Source folders: $IMAGEFOLDER/<projectId>/<sampleId>
# 4. Snapshots existing files at launch; new files are always uploaded first
# 5. Re-scans after every upload: new files (JSON → JPG → JP2), then existing (JSON → JPG → JP2)
# 6. Deletes local file on successful upload
# 7. Preserves folder hierarchy in S3
#
# Notes:
# - Requires Python3 (for JSON parsing)
# - Requires s3cmd:
#      sudo apt install s3cmd -y
#      s3cmd --configure
#           Access Key: xxx
#           Secret Key: xxx
#           Default Region: eu-west-3
#
#
# FREE TIP: simulate internet connection latency and packet loss (for test purposes)
#    → Ethernet: sudo tc qdisc add dev eth0 root netem delay 200ms loss 30%
#    → WiFi: sudo tc qdisc add dev wlan0 root netem delay 200ms loss 30%
#    → Back to normal: sudo tc qdisc del dev eth0 root netem
##########################################################

# -----------------------------
# 0. Variables
# -----------------------------
CONFIG_DIR="$HOME/Scanorhize/ConfigFile"
IMAGEFOLDER="/media/pi/Image"
S3_BUCKET="s3://humeos-images-landing"   # S3 bucket
EXISTING_FILES=""           # populated once at first launch
LOG_DIR="$HOME/Scanorhize/Log"
LOG_FILE=""                 # set after internet check (NTP synced)

while true; do
    echo ""
    echo "======================================"
    echo "======================================"
    echo "======================================"
    echo $(date)
    echo " Scanorhize Multi-Scanner S3 Sync Start"
    echo " Config JSONs: $CONFIG_DIR/Scanner-*.json"
    echo " Image folder: $IMAGEFOLDER"
    echo " Destination: $S3_BUCKET"
    echo "======================================"
    echo ""

    # -----------------------------
    # 1. Wait for internet connection
    # -----------------------------
    echo "[0/5] Checking internet connection..."
    while true; do
        if curl -s --max-time 5 -I https://clients3.google.com/generate_204 | grep -q "HTTP/.* 204"; then
            echo "✔ Internet connection detected."
            # Redirect to dated log now that NTP has had time to sync
            NEW_LOG="$LOG_DIR/upload-pictures-$(date +%Y-%m-%d).log"
            if [ "$NEW_LOG" != "$LOG_FILE" ]; then
                LOG_FILE="$NEW_LOG"
                mkdir -p "$LOG_DIR"
                exec >> "$LOG_FILE" 2>&1
            fi
            break
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') ⏳ No internet connection. Retrying in 5 seconds..."
            sleep 5
        fi
    done

    # -----------------------------
    # 2. Discover scanners from JSON files
    # -----------------------------
    echo "[1/5] Discovering scanners from JSON files..."

    SCANNERS=$(python3 - <<PYTHON
import json, glob, os, sys
config_dir = os.path.expanduser("$CONFIG_DIR")
for f in glob.glob(os.path.join(config_dir, "Scanner-*.json")):
    try:
        data = json.load(open(f))
        pid = data.get("projectId")
        sid = data.get("sampleId")
        if pid and sid:
            print(f"{pid}|{sid}")
    except Exception as e:
        print(f"Warning: Failed to parse {f}: {e}", file=sys.stderr)
PYTHON
)

    if [ -z "$SCANNERS" ]; then
        echo "❌ ERROR: No valid scanner JSON files found in $CONFIG_DIR"
        sleep 10
        continue
    fi

    echo "✔ Scanner definitions found:"
    echo "$SCANNERS" | while IFS='|' read -r pid sid; do
        echo "   - projectId=$pid sampleId=$sid"
    done

    # -----------------------------
    # 3. Build source folders
    # -----------------------------
    echo ""
    echo "[2/5] Resolving source folders..."

    SOURCES=()
    while IFS='|' read -r pid sid; do
        DIR="$IMAGEFOLDER/$pid/$sid"
        if [ -d "$DIR" ]; then
            echo "✔ Found folder: $DIR"
            SOURCES+=("$DIR")
        else
            echo "⚠ Missing folder: $DIR (ignored)"
        fi
    done <<< "$SCANNERS"

    if [ ${#SOURCES[@]} -eq 0 ]; then
        echo "❌ ERROR: No valid source folders found"
        sleep 10
        continue
    fi

    echo ""
    echo "✔ Active source folders:"
    for s in "${SOURCES[@]}"; do
        echo "   - $s"
    done

    # -----------------------------
    # 3b. Snapshot existing files once at launch (used to prioritize new files)
    # -----------------------------
    if [ -z "$EXISTING_FILES" ]; then
        EXISTING_FILES=$(mktemp)
        find "${SOURCES[@]}" -type f \( -name "*.json" -o -name "*.jpg" -o -name "*.jp2" \) \
            >> "$EXISTING_FILES" 2>/dev/null
        echo "✔ Snapshot: $(wc -l < "$EXISTING_FILES") existing files recorded at launch"
    fi

    # -----------------------------
    # 4. Function: upload all files one at a time, re-scanning after each upload.
    #    Priority order on every scan: new files first, then existing (each group JSON → JPG → JP2, newest first).
    # -----------------------------
    sync_one_by_one () {
        local PATTERNS=("*.json" "*.jpg" "*.jp2")
        local LABELS=("JSON" "JPG" "JP2")

        echo ""
        echo "======================================"
        echo "[SYNC] Starting upload pipeline (new files first, then existing — JSON → JPG → JP2)"
        echo "======================================"

        while true; do
            # Re-scan after every upload: new files take priority over files present at launch
            FILE=""
            LABEL=""
            for PHASE in new existing; do
                for i in 0 1 2; do
                    CANDIDATE=$(find "${SOURCES[@]}" -type f -name "${PATTERNS[$i]}" -printf '%T@ %p\n' 2>/dev/null \
                        | sort -nr | cut -d' ' -f2- | while read -r path; do
                            if [ "$PHASE" = "new" ] && ! grep -qxF "$path" "$EXISTING_FILES" 2>/dev/null; then
                                echo "$path"; break
                            elif [ "$PHASE" = "existing" ] && grep -qxF "$path" "$EXISTING_FILES" 2>/dev/null; then
                                echo "$path"; break
                            fi
                        done | head -1)
                    if [ -n "$CANDIDATE" ]; then
                        FILE="$CANDIDATE"
                        LABEL="${LABELS[$i]}"
                        break 2
                    fi
                done
            done

            [ -z "$FILE" ] && { echo "✔ No more files to sync"; break; }

            REL_PATH="${FILE#$IMAGEFOLDER/}"
            S3_DEST="$S3_BUCKET/$REL_PATH"
            echo ""
            echo "[$LABEL] Uploading: $REL_PATH → $S3_DEST"

            if s3cmd put "$FILE" "$S3_DEST"; then
                echo "    ✔  Upload successful"
                echo "    → Deleting file"
                rm "$FILE"
            else
                echo "    ❌ Upload failed! Stopping sync"
                echo "    → Keeping file"
                break
            fi
        done
    }

    # -----------------------------
    # 5. Run sync pipeline
    # -----------------------------
    echo ""
    echo "[3/5] Starting sync pipeline..."

    sync_one_by_one

    echo ""
    echo "======================================"
    echo "✔ S3 SYNC COMPLETE"
    echo " Bucket: $S3_BUCKET"
    echo "======================================"


    sleep 10  # wait 10 seconds before next upload
done
