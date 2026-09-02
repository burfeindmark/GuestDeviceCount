#!/bin/bash
# Installation script for Guest Device Counter on Debian/Raspberry Pi
# This script sets up the service and all dependencies and uses a virtualenv at /opt/guest-device-counter/venv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="guest-device-counter"
INSTALL_DIR="/opt/guest-device-counter"
VENV_DIR="$INSTALL_DIR/venv"
CONFIG_DIR="/etc/guest-device-counter"
DATA_DIR="/var/lib/guest-device-counter"
LOG_DIR="/var/log/guest-device-counter"
USER="$SERVICE_NAME"
GROUP="$SERVICE_NAME"

echo "=========================================="
echo "Guest Device Counter Installation (with venv)"
echo "=========================================="

# Must be root
if [[ $(id -u) -ne 0 ]]; then
    echo "This script must be run as root (use: sudo ./install.sh)"
    exit 1
fi

# Basic OS check (warning only)
if ! grep -qi 'debian\|ubuntu\|raspberry' /etc/os-release; then
    echo "Warning: This script is designed for Debian/Raspberry Pi" >&2
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/10] Installing system packages (apt)"
apt-get update
apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-distutils \
    python3-dev \
    git \
    arp-scan \
    dnsmasq \
    net-tools \
    build-essential \
    ca-certificates

# Create service user if needed
echo "[2/10] Ensuring service user exists"
if ! id "$USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$USER"
    echo "Created user: $USER"
else
    echo "User already exists: $USER"
fi

# Create directories
echo "[3/10] Creating directories"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"

chown root:root "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# Copy code into install dir
echo "[4/10] Copying application files to $INSTALL_DIR"
rsync -a --exclude='.git' --delete "$SCRIPT_DIR/" "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"

# Create virtual environment and install Python deps
echo "[5/10] Creating virtualenv at $VENV_DIR and installing Python dependencies"
python3 -m venv "$VENV_DIR"
# Ensure pip is up to date inside venv
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# Install package in editable mode inside venv (so CLI entrypoints are available)
"$VENV_DIR/bin/pip" install -e "$INSTALL_DIR"

# Setup ownership for runtime dirs
echo "[6/10] Setting ownership and permissions"
chown -R "$USER":"$GROUP" "$DATA_DIR" || true
chown -R "$USER":"$GROUP" "$LOG_DIR" || true
mkdir -p "$DATA_DIR/reports"
chown -R "$USER":"$GROUP" "$DATA_DIR/reports" || true

# Copy default configuration if missing
echo "[7/10] Installing configuration"
if [ ! -f "$CONFIG_DIR/config.yml" ]; then
    cp "$INSTALL_DIR/config.yml" "$CONFIG_DIR/config.yml"
    chmod 640 "$CONFIG_DIR/config.yml"
    chown "$USER":"$GROUP" "$CONFIG_DIR/config.yml" || true
    echo "Configuration created at $CONFIG_DIR/config.yml"
else
    echo "Configuration already exists at $CONFIG_DIR/config.yml"
fi

# Install systemd service (use venv python path in ExecStart)
echo "[8/10] Installing systemd service"
SERVICE_DEST="/etc/systemd/system/$SERVICE_NAME.service"
cp "$INSTALL_DIR/guest-device-counter.service" "$SERVICE_DEST"
# Update ExecStart to use venv python
sed -i "s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python -m guest_device_counter.app -c $CONFIG_DIR/config.yml|" "$SERVICE_DEST"
chmod 644 "$SERVICE_DEST"

# Reload systemd
systemctl daemon-reload

# Enable & start service
echo "[9/10] Enabling and starting $SERVICE_NAME"
systemctl enable "$SERVICE_NAME" || true
systemctl restart "$SERVICE_NAME" || systemctl start "$SERVICE_NAME"

# Logrotate
echo "[10/10] Setting up log rotation"
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

# Final messages
echo ""
echo "=========================================="
echo "Installation Complete"
echo "Reports: $DATA_DIR/reports"
echo "Database: $DATA_DIR/devices.db"
echo "Service: $SERVICE_NAME (systemd)"
echo "=========================================="

echo "To view logs: sudo journalctl -u $SERVICE_NAME -f"

exit 0
