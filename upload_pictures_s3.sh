#!/bin/bash

##########################################################
# Humeos Multi-Scanner Sync Script to S3
#
# This script:
# 1. Discovers all scanners from JSON files in $CONFIG_DIR
# 2. Reads projectId and sampleId from each scanner JSON files
# 3. Source folders: $IMAGEFOLDER/<projectId>/<sampleId>
# 4. Syncs files to S3 in order: JSON → JPG → JP2
# 5. Sorts files by newest first
# 6. Preserves folder hierarchy in S3
#
# Notes:
# - Requires Python3 (for JSON parsing)
# - Requires AWS CLI:
#      sudo apt install awscli -y
#      aws configure
#           AWS Access Key ID [None]: xxx
#           AWS Secret Access Key [None]: xxx
#           Default region name [None]: eu-west-3
#           Default output format [None]: json
#
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
S3_BUCKET="s3://humeos-test"   # S3 bucket

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
        exit 1
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
        exit 1
    fi

    echo ""
    echo "✔ Active source folders:"
    for s in "${SOURCES[@]}"; do
        echo "   - $s"
    done

    # -----------------------------
    # 4. Function to sync files by type to S3
    # -----------------------------
    sync_sorted_s3 () {
        PATTERN="$1"
        LABEL="$2"

        echo ""
        echo "======================================"
        echo "[SYNC] $LABEL files ($PATTERN)"
        echo "======================================"

        FILE_LIST=$(mktemp)

        # Collect files from all sources
        for SRC in "${SOURCES[@]}"; do
            echo "Scanning: $SRC"
            find "$SRC" -type f -name "$PATTERN" -printf '%T@ %p\n' >> "$FILE_LIST"
        done

        COUNT=$(wc -l < "$FILE_LIST")
        echo "✔ Total $LABEL files found: $COUNT"

        if [ "$COUNT" -eq 0 ]; then
            echo "⚠ No $LABEL files to sync"
            rm -f "$FILE_LIST"
            return
        fi

        echo "Sorting newest first and uploading to S3..."

        # Loop through files, newest first
        sort -nr "$FILE_LIST" | cut -d' ' -f2- | while read -r FILE; do
            # Preserve projectId/sampleId structure relative to IMAGEFOLDER
            REL_PATH="${FILE#$IMAGEFOLDER/}"
            S3_DEST="$S3_BUCKET/$REL_PATH"
            echo ""
            echo "Uploading: $REL_PATH → $S3_DEST"
            if aws s3 cp "$FILE" "$S3_DEST" --only-show-errors; then
                echo "    ✔  Upload successful"
                echo "    → Deleting file"
                rm "$FILE" #Remove file from USB drive
            else
                echo "    ❌ Upload failed!"
                echo "    → Keeping file"
            fi
            
        done

        rm -f "$FILE_LIST"
        echo "✔ Done syncing $LABEL"
    }

    # -----------------------------
    # 5. Run sync pipeline in priority order
    # .json first, then .jpg files, and .jp2 files
    # -----------------------------
    echo ""
    echo "[3/5] Starting sync pipeline..."

    sync_sorted_s3 "*.json" "JSON"
    sync_sorted_s3 "*.jpg" "JPG"
    sync_sorted_s3 "*.jp2" "JP2"

    echo ""
    echo "======================================"
    echo "✔ S3 SYNC COMPLETE"
    echo " Bucket: $S3_BUCKET"
    echo "======================================"


    sleep 10  # wait 10 seconds before next upload
done
