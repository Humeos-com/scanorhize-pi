#!/bin/bash
# =============================================================================
# Raspberry Pi 5 Migration Script - Scanorhize
# Source: doc_repo_pi5 + MigrationWittypi4vers5
# Usage : sudo bash migration_pi5.sh
# =============================================================================

set -e  # Exit on error

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\e[94m'
NC='\033[0m'

log()     { echo -e "${GREEN}[OK]${NC} $1"; }
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
section() { echo -e "\n${BLUE}========================================${NC}"; \
            echo -e "${BLUE}  $1${NC}"; \
            echo -e "${BLUE}========================================${NC}"; }

# -----------------------------------------------------------------------------
# Root check
# -----------------------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root: sudo bash $0"
    exit 1
fi

# -----------------------------------------------------------------------------
# SSID selection
# -----------------------------------------------------------------------------
section "Access Point SSID"

DEFAULT_SSID="Scanorhize_Hub"
echo ""
echo "  Default SSID: $DEFAULT_SSID"
echo ""
read -p "  Enter the AP SSID (press Enter to keep default): " INPUT_SSID

if [ -z "$INPUT_SSID" ]; then
    AP_SSID="$DEFAULT_SSID"
    info "Using default SSID: $AP_SSID"
else
    AP_SSID="$INPUT_SSID"
    info "Using SSID: $AP_SSID"
fi

# =============================================================================
# 1. NETWORKMANAGER DISPATCHER
# =============================================================================
section "1/4 - NetworkManager dispatcher"

DISPATCHER_FILE="/etc/NetworkManager/dispatcher.d/99-scanorhize"

if [ -f "$DISPATCHER_FILE" ]; then
    # Comment out the line that starts shut-connection.service
    if grep -q "systemctl start shut-connection" "$DISPATCHER_FILE"; then
        sed -i 's/^\(.*systemctl start shut-connection.*\)$/#\1  # disabled - pi5 migration/' "$DISPATCHER_FILE"
        log "shut-connection line commented in $DISPATCHER_FILE"
    else
        warn "shut-connection line already commented or not found in $DISPATCHER_FILE"
    fi
else
    warn "Dispatcher file $DISPATCHER_FILE not found - check the path"
fi

# =============================================================================
# 2. 4G EC25-E CONNECTION
# =============================================================================
section "2/4 - 4G EC25-E connection"

# Create EC25-E profile if it does not exist
if nmcli connection show "EC25-E" &>/dev/null; then
    warn "EC25-E profile already exists, deleting and recreating..."
    nmcli connection delete "EC25-E"
fi
info "Creating GSM connection profile EC25-E..."
nmcli connection add type gsm ifname cdc-wdm0 con-name "EC25-E"
log "EC25-E profile created"

# Set low route metric to give 4G priority over other interfaces
info "Setting 4G route priority (route-metric 500)..."
nmcli connection modify "EC25-E" ipv4.route-metric 500
log "EC25-E route-metric set to 500"

# Bring up the 4G connection
info "Bringing up EC25-E connection (timeout 30s)..."
# Show a countdown while waiting for the connection
(
    for i in $(seq 30 -1 1); do
        printf "\r  [INFO] Waiting for EC25-E... %2ds remaining" "$i"
        sleep 1
    done
) &
COUNTDOWN_PID=$!

timeout 30 nmcli connection up "EC25-E" && log "EC25-E connected" || warn "EC25-E activation failed or timed out after 30s (is the modem plugged in?)"

kill $COUNTDOWN_PID 2>/dev/null
printf "\r%50s\r" " "  # Clear the countdown line

# =============================================================================
# 3. WIFI ACCESS POINT
# =============================================================================
section "3/4 - Wi-Fi access point: $AP_SSID"

if nmcli connection show "hub_AP" &>/dev/null; then
    warn "hub_AP profile already exists, updating parameters..."
    # Update SSID in case it changed
    nmcli con modify hub_AP 802-11-wireless.ssid "$AP_SSID"
else
    info "Creating Wi-Fi access point..."
    nmcli con add type wifi ifname wlan0 mode ap con-name hub_AP ssid "$AP_SSID" autoconnect yes
    log "Access point hub_AP created"
fi

# Share the 4G internet connection over Wi-Fi
info "Configuring connection sharing (4G internet -> Wi-Fi)..."
nmcli con modify hub_AP ipv4.method shared ipv4.addresses 192.168.4.1/24
nmcli con modify hub_AP wifi-sec.key-mgmt wpa-psk
nmcli con modify hub_AP wifi-sec.psk "Scanorhize"
nmcli con modify hub_AP connection.autoconnect yes

log "Access point configured: SSID=$AP_SSID IP=192.168.4.1 autoconnect=yes"

info "Bringing up access point..."
nmcli con up hub_AP || warn "hub_AP activation failed (is wlan0 available?)"

# =============================================================================
# 4. WITTYPI 4 -> 5 MIGRATION
# =============================================================================
section "4/4 - WittyPi 4 -> WittyPi 5 migration"

# --- 4a. Stop and disable WP4 service ---
info "Stopping wittypi service (WP4)..."
systemctl stop wittypi.service 2>/dev/null && log "wittypi service stopped" \
    || warn "wittypi service not found or already stopped"

info "Disabling wittypi service at boot..."
systemctl disable wittypi.service 2>/dev/null && log "wittypi service disabled" \
    || warn "wittypi service not found or already disabled"

# --- 4b. Remove WP4 files ---
info "Removing WP4 files..."

[ -f /etc/systemd/system/wittypi.service ] \
    && rm /etc/systemd/system/wittypi.service \
    && log "Removed /etc/systemd/system/wittypi.service" \
    || warn "/etc/systemd/system/wittypi.service not found"

[ -f /etc/init.d/wittypi ] \
    && rm /etc/init.d/wittypi \
    && log "Removed /etc/init.d/wittypi" \
    || warn "/etc/init.d/wittypi not found"

[ -d ~/wittypi ] \
    && rm -rf ~/wittypi \
    && log "Removed ~/wittypi directory" \
    || warn "~/wittypi directory not found"

systemctl daemon-reload
log "systemd daemon reloaded"

# --- 4c. Install WP5 ---
# The .deb package must be compiled on your PC and placed in
# C:\Users\Wakaw\Desktop\Scanorhize_Transfert before running this script.
# It will be picked up from /home/pi/Scanorhize after the scp transfer.
section "4c - WP5 deb install"

WP5_DEB=$(ls /home/pi/Scanorhize/*.deb 2>/dev/null | head -n 1)

if [ -n "$WP5_DEB" ]; then
    info "Found deb package: $WP5_DEB"
    dpkg -i "$WP5_DEB"
    log "WP5 installed ($WP5_DEB)"
else
    error "No .deb file found in /home/pi/Scanorhize"
    error "Build the package on your PC and transfer it via Scanorhize_Transfert before running this script"
    exit 1
fi

systemctl daemon-reload
systemctl restart wp5d.service
log "wp5d service started"

# --- 4c-2. WP5 I2C configuration ---
section "4c-2 - WP5 I2C configuration"

WP5_ADDR=0x51
WP5_BUS=1

# Helper: write one register with a small delay to avoid flooding the I2C bus
wp5set() {
    local reg=$1
    local val=$2
    local desc=$3
    i2cset -y $WP5_BUS $WP5_ADDR "$reg" "$val"
    sleep 0.05
    log "WP5 reg#$reg = $val  ($desc)"
}

# Check that the WP5 is reachable before writing
if ! i2cget -y $WP5_BUS $WP5_ADDR 0 &>/dev/null; then
    warn "WP5 not detected on I2C bus $WP5_BUS addr $WP5_ADDR - skipping configuration"
    warn "Make sure wp5d.service is running and I2C is enabled"
else
    info "Configuring WP5 via I2C..."

    # Power source priority: 1 = VIN first
    wp5set 24 1 "power source priority = VIN first"

    # LED pulse interval: 3 seconds
    wp5set 19 3 "LED pulse interval = 3s"

    # LED on duration: 100ms
    wp5set 20 100 "LED on duration = 100ms"

    # Startup delay on power connection: 250 seconds
    wp5set 17 250 "startup delay = 250 seconds"

    # Delay between Pi shutdown and power cut: 5 seconds
    wp5set 18 5 "shutdown delay after button = 5s"

    # Low voltage threshold: 10.0V -> value = 10.0 * 10 = 100
    wp5set 22 100 "low voltage threshold = 10.0V"

    # Recovery voltage threshold: 10.5V -> value = 10.5 * 10 = 105
    wp5set 23 105 "recovery voltage threshold = 10.5V"

    # Over temperature action: 2 = shutdown
    wp5set 42 2 "over temperature action = shutdown"

    # Over temperature threshold: 70 degrees C
    wp5set 43 70 "over temperature threshold = 70C"

    # Below temperature action: 0 = do nothing (disabled)
    wp5set 40 0 "below temperature action = disabled"

    # Log to file: 1 = allowed
    wp5set 30 1 "log to file = enabled"

    log "WP5 I2C configuration complete"
fi

# --- 4c-3. Set I2C baudrate to 50kHz for WP5 reliability ---
section "4c-3 - I2C baudrate (50kHz)"

CONFIG_FILE="/boot/firmware/config.txt"
BAUDRATE_LINE="dtparam=i2c_arm_baudrate=50000"

if grep -qF "$BAUDRATE_LINE" "$CONFIG_FILE"; then
    warn "$BAUDRATE_LINE already set in $CONFIG_FILE"
else
    echo "" >> "$CONFIG_FILE"
    echo "$BAUDRATE_LINE" >> "$CONFIG_FILE"
    log "Added $BAUDRATE_LINE to $CONFIG_FILE"
fi

# --- 4d. Create scanorhize-startup service ---
section "4d - scanorhize-startup service"

SERVICE_FILE="/etc/systemd/system/scanorhize-startup.service"

if [ -f "$SERVICE_FILE" ]; then
    warn "scanorhize-startup service already exists, overwriting..."
fi
info "Creating $SERVICE_FILE..."
if true; then

    # Create log directory if it does not exist
    mkdir -p /home/pi/Scanorhize/Log
    chown pi:pi /home/pi/Scanorhize/Log

    cat > "$SERVICE_FILE" << 'SVCEOF'
[Unit]
Description=Start Scanorhize
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Scanorhize
StartLimitInterval=30
StartLimitBurst=5
ExecStartPre=/usr/bin/rsync -av /home/pi/Scanorhize/static/ /home/pi/Scanorhize/images/
ExecStart=/usr/bin/python3 -u /home/pi/Scanorhize/ScanorhizeStart.py
Restart=always
# Logging handled by Python FileHandler in ConfigApp.py -> Log/ScanorhizeStart.log

[Install]
WantedBy=multi-user.target
SVCEOF
    systemctl enable scanorhize-startup.service
    log "scanorhize-startup service created and enabled"
fi


# =============================================================================
# 5. CREATE UPLOAD-PICTURES SERVICE
# =============================================================================
section "5 - upload-pictures service"

SERVICE_FILE="/etc/systemd/system/upload-pictures.service"

if [ -f "$SERVICE_FILE" ]; then
    warn "upload-pictures service already exists, overwriting..."
fi
info "Creating $SERVICE_FILE..."
if true; then

    cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=Upload pictures
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Scanorhize
ExecStartPre=/bin/chmod +x /home/pi/Scanorhize/upload_pictures_s3.sh
ExecStart=/bin/bash -c 'sleep 5 && /home/pi/Scanorhize/upload_pictures_s3.sh >> /home/pi/Scanorhize/Log/upload-pictures-$(date +%%Y-%%m-%%d).log 2>&1'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF
    systemctl enable upload-pictures.service
    log "upload-pictures service created and enabled"
fi


# =============================================================================
# 6. PYTHON FILES TRANSFER NOTE
# =============================================================================
section "6 - Python files transfer (manual step)"

echo ""
info "Python file changes are NOT applied automatically by this script."
info "To transfer modified files from your Windows desktop, run:"
echo ""
echo "  scp -r C:\\Users\\Wakaw\\Desktop\\Scanorhize_Transfert\\* pi@192.168.4.1:/home/pi/Scanorhize/"
echo ""
info "If connected via Wi-Fi on $AP_SSID, the Pi IP is 192.168.4.1"
info "If connected via LAN, replace 192.168.4.1 with the Pi LAN IP"
echo ""

# =============================================================================
# SUMMARY
# =============================================================================
section "Summary"

echo ""
echo "  [OK] NetworkManager dispatcher: shut-connection line commented"
echo "  [OK] 4G EC25-E profile created (APN orange, priority routing)"
echo "  [OK] Access point $AP_SSID (192.168.4.1, WPA2, autoconnect yes)"
echo "  [OK] wittypi (WP4) service stopped and disabled"
echo "  [OK] WP4 files removed"
echo "  [OK] WittyPi 5 installed (wp5d.service running)"
echo "  [OK] scanorhize-startup service created"
echo "  [OK] upload-pictures service created"
echo ""
warn "Remember to transfer the modified Python files (see section 6)"
warn "A reboot is recommended to validate all changes"
echo ""
read -p "Reboot now? [y/N] " REBOOT
if [[ "$REBOOT" =~ ^[yY]$ ]]; then
    log "Rebooting in 5 seconds..."
    sleep 5
    reboot
fi
