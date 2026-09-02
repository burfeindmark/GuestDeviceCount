#!/bin/bash
# Installation script for Guest Device Counter on Debian/Raspberry Pi
# This script sets up the service and all dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="guest-device-counter"
INSTALL_DIR="/opt/guest-device-counter"
CONFIG_DIR="/etc/guest-device-counter"
DATA_DIR="/var/lib/guest-device-counter"
LOG_DIR="/var/log/guest-device-counter"
USER="$SERVICE_NAME"
GROUP="$SERVICE_NAME"

echo "=========================================="
echo "Guest Device Counter Installation"
echo "=========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use: sudo ./install.sh)"
   exit 1
fi

# Check OS
if ! grep -qi 'debian\|ubuntu\|raspberry' /etc/os-release; then
    echo "Warning: This script is designed for Debian/Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/7] Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    arp-scan \
    dnsmasq \
    net-tools \
    build-essential

echo "[2/7] Creating service user..."
if ! id "$USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false "$USER"
    echo "Created user: $USER"
else
    echo "User already exists: $USER"
fi

echo "[3/7] Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"

chmod 750 "$DATA_DIR"
chmod 750 "$LOG_DIR"
chown "$USER:$GROUP" "$DATA_DIR"
chown "$USER:$GROUP" "$LOG_DIR"

echo "[4/7] Installing Python package..."
cd "$SCRIPT_DIR"
pip3 install --upgrade pip setuptools wheel
pip3 install -r requirements.txt
pip3 install -e .

echo "[5/7] Copying configuration..."
if [ ! -f "$CONFIG_DIR/config.yml" ]; then
    cp "$SCRIPT_DIR/config.yml" "$CONFIG_DIR/config.yml"
    echo "Configuration file created: $CONFIG_DIR/config.yml"
    echo "Please edit this file to configure your venue and network settings"
else
    echo "Configuration file already exists: $CONFIG_DIR/config.yml"
    echo "Review it to ensure settings are correct"
fi

chmod 640 "$CONFIG_DIR/config.yml"
chown "$USER:$GROUP" "$CONFIG_DIR/config.yml"

echo "[6/7] Installing systemd service..."
cp "$SCRIPT_DIR/guest-device-counter.service" /etc/systemd/system/
systemctl daemon-reload
chmod 644 /etc/systemd/system/guest-device-counter.service

echo "[7/7] Setting up log rotation..."
cat > "/etc/logrotate.d/$SERVICE_NAME" << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $USER $GROUP
    sharedscripts
}
EOF

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit configuration: sudo nano $CONFIG_DIR/config.yml"
echo "2. Enable the service: sudo systemctl enable $SERVICE_NAME"
echo "3. Start the service: sudo systemctl start $SERVICE_NAME"
echo "4. Check status: sudo systemctl status $SERVICE_NAME"
echo "5. View logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Reports will be saved to: $DATA_DIR/reports/"
echo "Database file: $DATA_DIR/devices.db"
echo ""
