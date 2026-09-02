# Quick Start Guide

## 🚀 5-Minute Setup

### Prerequisites
- Raspberry Pi 3B+ or Debian/Ubuntu system
- Network connection to guest network VLAN
- SSH access with sudo privileges

### Installation

```bash
# 1. Get the code
git clone https://github.com/burfeindmark/GuestDeviceCount.git
cd GuestDeviceCount

# 2. Run installer (one command!)
sudo ./install.sh

# 3. Configure your venue
sudo nano /etc/guest-device-counter/config.yml
# Edit: venue_name, network_interface

# 4. Start the service
sudo systemctl enable guest-device-counter
sudo systemctl start guest-device-counter

# 5. Verify it's working
sudo systemctl status guest-device-counter
```

## 📊 Quick Commands

```bash
# View devices currently on network
gdc-query guests

# Get statistics
gdc-query stats --days 1

# Look up a specific device
gdc-query history aa:bb:cc:dd:ee:ff

# Export data
gdc-query export devices.csv

# Check service logs
sudo journalctl -u guest-device-counter -f
```

## 📋 What Happens Next

✅ **Automatic (every 15 min):**
- Scans guest network for devices
- Logs MAC addresses, IPs, hostnames
- Tracks device presence

✅ **Daily (at 9:00 AM):**
- Generates PDF report from previous day
- Saved to `/var/lib/guest-device-counter/reports/`

✅ **Ongoing:**
- After 5 consecutive days, device marked as "employee"
- Employee devices automatically filtered from reports
- Reports show only guest device analytics

## 📁 Key Files

- **Reports:** `/var/lib/guest-device-counter/reports/`
- **Database:** `/var/lib/guest-device-counter/devices.db`
- **Config:** `/etc/guest-device-counter/config.yml`
- **Logs:** `sudo journalctl -u guest-device-counter`

## 🔧 Customize Reports

Edit `/etc/guest-device-counter/config.yml`:

```yaml
# Daily reports at 8 AM
daily_report_time: "08:00"

# Weekly reports on Monday at 9 AM
weekly_report_day: 0
weekly_report_time: "09:00"

# Monthly reports on the 1st at 9 AM
monthly_report_day: 1
monthly_report_time: "09:00"

# Scan more frequently
scan_interval_minutes: 10  # instead of 15

# Change employee detection threshold
employee_threshold_days: 3  # instead of 5
```

Then restart:
```bash
sudo systemctl restart guest-device-counter
```

## ✅ Troubleshooting

### Service won't start?
```bash
sudo journalctl -u guest-device-counter -n 50
```

### No devices found?
```bash
# Check network interface
ip link show

# Manual scan test
sudo arp-scan --localnet
```

### Reports not generating?
```bash
# Generate one manually
guest-device-counter --daily-report

# Check report directory
ls -l /var/lib/guest-device-counter/reports/
```

## 📚 More Info

- Full docs: `README.md`
- Deployment guide: `DEPLOYING.md`
- Run tests: `python3 -m unittest discover`

---

**That's it! Your venue device counter is now live! 🎉**
