# Deployment Guide for Guest Device Counter

## Overview
This guide covers deploying Guest Device Counter on a Raspberry Pi or Debian server connected to your guest network.

## Pre-Deployment Checklist

- [ ] Raspberry Pi 3B+ or newer (or Debian/Ubuntu system)
- [ ] Network connectivity to guest network VLAN
- [ ] SSH access to the device
- [ ] Root/sudo privileges
- [ ] Stable power supply
- [ ] Static IP address configured (recommended)

## Step 1: Initial Setup

### Prepare Raspberry Pi

If starting fresh, install Raspberry Pi OS:
1. Download from https://www.raspberrypi.org/software/
2. Flash to microSD card using Balena Etcher or similar
3. Enable SSH in raspi-config: `sudo raspi-config` → Interfacing Options → SSH

### Update System

```bash
ssh pi@raspberry.local  # or your device IP

sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git
```

### Configure Network (if needed)

Ensure the device is on your guest network VLAN. Edit `/etc/dhcpcd.conf`:

```bash
sudo nano /etc/dhcpcd.conf

# Add static IP (optional but recommended):
interface eth0
static ip_address=192.168.100.5/24
static routers=192.168.100.1
static domain_name_servers=192.168.100.1
```

Then reboot:
```bash
sudo reboot
```

## Step 2: Clone Repository

```bash
cd /home/pi
git clone https://github.com/burfeindmark/GuestDeviceCount.git
cd GuestDeviceCount
```

## Step 3: Run Installation

```bash
sudo chmod +x install.sh
sudo ./install.sh
```

This script will:
- Install all system dependencies
- Create service user `guest-device-counter`
- Install Python package
- Set up directories and permissions
- Install systemd service
- Configure log rotation

## Step 4: Configuration

Edit the configuration file:

```bash
sudo nano /etc/guest-device-counter/config.yml
```

Key settings to configure:

```yaml
# Name your venue
venue_name: "My Convention Center"

# Set the network interface (eth0 for wired, wlan0 for wireless)
network_interface: "eth0"

# Optional: specify network range for scanning
network_range: null  # or "192.168.100.0/24"

# Scan interval in minutes
scan_interval_minutes: 15

# Employee detection threshold
employee_threshold_days: 5

# Report timing (24-hour format)
daily_report_time: "09:00"
weekly_report_day: 0  # 0=Monday
```

Save and exit: `Ctrl+X`, `Y`, `Enter`

## Step 5: Verify Configuration

Check network interface:
```bash
ip link show
ip addr show
```

Test ARP scanning:
```bash
sudo arp-scan --localnet
```

Test DHCP lease detection:
```bash
sudo cat /var/lib/dnsmasq/dnsmasq.leases
```

## Step 6: Start Service

```bash
# Enable service to start on boot
sudo systemctl enable guest-device-counter

# Start the service
sudo systemctl start guest-device-counter

# Check status
sudo systemctl status guest-device-counter

# View logs
sudo journalctl -u guest-device-counter -f
```

Wait 2-3 minutes and check logs for any errors.

## Step 7: Verify Operation

```bash
# Check database creation
ls -lh /var/lib/guest-device-counter/

# Query devices (after first scan)
gdc-query guests --limit 10

# View statistics
gdc-query stats --days 1
```

## Deployment Scenarios

### Scenario 1: Fresh Raspberry Pi Installation

**Time: ~30 minutes**

```bash
# 1. Flash Raspberry Pi OS to microSD
# 2. SSH into device
# 3. Clone and install
git clone https://github.com/burfeindmark/GuestDeviceCount.git
cd GuestDeviceCount
sudo ./install.sh

# 4. Configure
sudo nano /etc/guest-device-counter/config.yml

# 5. Start
sudo systemctl start guest-device-counter
```

### Scenario 2: Existing Debian Server

```bash
cd /opt
sudo git clone https://github.com/burfeindmark/GuestDeviceCount.git
cd GuestDeviceCount
sudo ./install.sh
```

### Scenario 3: Docker Deployment

```bash
docker build -t guest-device-counter .
docker run -d \
  --name gdc \
  --network host \
  -v /etc/guest-device-counter:/etc/guest-device-counter \
  -v /var/lib/guest-device-counter:/var/lib/guest-device-counter \
  guest-device-counter
```

## Post-Deployment

### Monitor First Week

- Check logs daily: `sudo journalctl -u guest-device-counter -n 100`
- Verify reports generate: `ls /var/lib/guest-device-counter/reports/`
- Query device counts: `gdc-query stats`

### Backup Database

```bash
sudo cp /var/lib/guest-device-counter/devices.db \
  /var/lib/guest-device-counter/devices.db.backup
```

### Set Up Email Reports (Optional)

```bash
# Create report mailing script
sudo nano /usr/local/bin/mail-reports.sh

#!/bin/bash
REPORT_DIR="/var/lib/guest-device-counter/reports"
LATEST=$(ls -t $REPORT_DIR/daily_report_*.pdf | head -1)
echo "See attached daily report" | mail -s "Daily Device Report" \
  -a "$LATEST" admin@example.com
```

Schedule with cron:
```bash
sudo crontab -e
# Add: 10 9 * * * /usr/local/bin/mail-reports.sh
```

## Troubleshooting Deployments

### Service Won't Start

```bash
# Check logs
sudo journalctl -u guest-device-counter -n 50

# Verify Python installation
python3 -c "import guest_device_counter"

# Check permissions
sudo ls -l /var/lib/guest-device-counter
```

### No Devices Detected

```bash
# Verify network interface
ip link show

# Manual ARP scan
sudo arp-scan --localnet

# Check if DHCP is running
sudo systemctl status dnsmasq

# View DHCP leases
sudo cat /var/lib/dnsmasq/dnsmasq.leases
```

### Reports Not Generating

```bash
# Check cron/schedule
sudo systemctl status guest-device-counter

# Manually generate report
guest-device-counter --daily-report

# Check permissions
sudo ls -l /var/lib/guest-device-counter/reports/
```

### Database Locked Error

```bash
# Kill any stray processes
sudo pkill -f guest-device-counter

# Check database
sudo sqlite3 /var/lib/guest-device-counter/devices.db ".integrity_check"

# Restart service
sudo systemctl restart guest-device-counter
```

## Performance Tuning

### High CPU Usage

- Increase scan interval: `scan_interval_minutes: 30`
- Disable unused features in config
- Check for other processes: `top`

### High Memory Usage

- Archive old logs: `sudo journalctl --rotate && sudo journalctl --vacuum-time=7d`
- Trim database: `gdc-query cleanup --days 60`

### Slow Scanning

- Reduce scan range if possible
- Use `arp-scan` instead of full NMAP
- Check network latency

## Security Hardening

```bash
# Lock down file permissions
sudo chmod 700 /var/lib/guest-device-counter
sudo chmod 700 /etc/guest-device-counter

# Disable SSH password login (if using keys)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart ssh

# Enable firewall
sudo ufw enable
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow from 192.168.100.0/24 to any port 22

# Unattended updates
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## Maintenance Schedule

### Daily
- Monitor logs (automated alerts can be set up)
- Verify reports generated

### Weekly
- Check service status: `systemctl status guest-device-counter`
- Backup database if critical

### Monthly
- Archive and review reports
- Verify device counts are reasonable
- Trim database of old events: `gdc-query cleanup`
- Check disk space: `df -h`

### Quarterly
- Review employee detection thresholds
- Audit network connections
- Update system: `apt update && apt upgrade`

## Support & Troubleshooting

For detailed help:
```bash
# View full logs
sudo journalctl -u guest-device-counter --since "2 hours ago" -n 500

# Export device data
gdc-query export devices.csv

# Manual database query
sqlite3 /var/lib/guest-device-counter/devices.db
```

For issues: https://github.com/burfeindmark/GuestDeviceCount/issues

---

**Successfully deployed? Share your setup!** 🎉
