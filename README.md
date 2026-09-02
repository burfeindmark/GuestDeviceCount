# GuestDeviceCount

A comprehensive device counter and analytics tool for Guest Networks in public venues (convention centers, arenas, hotels, etc.).

This tool deploys on a Debian/Raspberry Pi system on the guest network VLAN to provide detailed reports on device connectivity, including MAC addresses, device types, and usage patterns.

## Features

✅ **Automatic Device Detection**
- ARP and DHCP lease scanning every 15 minutes (configurable)
- MAC address tracking with vendor identification
- Hostname and IP address logging
- Automatic device type detection (iPhone, Android, Windows, IoT, etc.)

✅ **Employee Device Filtering**
- Automatically marks devices as "employee" after 5 consecutive days
- Filters employee devices from guest reports
- Maintains separate tracking for employee vs. guest activity

✅ **Comprehensive Logging**
- Real-time connection event logging
- Daily presence tracking
- Complete device history in SQLite database
- Detailed connection timestamps

✅ **Professional PDF Reports**
- Daily reports (previous day summary)
- Weekly reports (7-day analytics)
- Monthly reports (30-day trends)
- Customizable report timing
- Statistics on peak usage times and device counts

✅ **Easy Deployment**
- Single-step installation on Debian/Raspberry Pi
- Systemd service integration
- Automatic log rotation
- Configuration via simple YAML file

## Hardware Requirements

- **Raspberry Pi 3B+** or better (or any Debian system)
- Ethernet connection to guest network VLAN
- 4GB+ microSD card (minimum 2GB)
- Internet access for initial setup

## Installation

### Quick Start

```bash
# Clone or download the repository
cd /path/to/GuestDeviceCount

# Run the installation script (requires sudo)
sudo ./install.sh

# Edit configuration for your venue
sudo nano /etc/guest-device-counter/config.yml

# Enable and start the service
sudo systemctl enable guest-device-counter
sudo systemctl start guest-device-counter

# Check status
sudo systemctl status guest-device-counter
```

### Manual Installation

```bash
# Install Python and dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-dev git arp-scan dnsmasq net-tools

# Install the package
sudo pip3 install -e .

# Copy service file
sudo cp guest-device-counter.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start the service
sudo systemctl start guest-device-counter
```

## Configuration

Edit `/etc/guest-device-counter/config.yml`:

```yaml
# Venue name for reports
venue_name: "My Convention Center"

# Network interface to monitor
network_interface: "eth0"

# Scan interval (minutes)
scan_interval_minutes: 15

# Days before marking device as employee
employee_threshold_days: 5

# Report generation times
enable_daily_reports: true
daily_report_time: "09:00"

enable_weekly_reports: true
weekly_report_day: 0  # Monday
weekly_report_time: "09:00"

enable_monthly_reports: true
monthly_report_day: 1
monthly_report_time: "09:00"
```

## Usage

### Service Management

```bash
# View service status
sudo systemctl status guest-device-counter

# View live logs
sudo journalctl -u guest-device-counter -f

# Stop the service
sudo systemctl stop guest-device-counter

# Restart the service
sudo systemctl restart guest-device-counter
```

### Manual Commands

```bash
# Run a single scan immediately
guest-device-counter --scan

# Generate reports manually
guest-device-counter --daily-report
guest-device-counter --weekly-report
guest-device-counter --monthly-report
```

### Data & Reports

- **Database**: `/var/lib/guest-device-counter/devices.db`
  - Contains all device records and connection logs
  - SQLite format, can be queried directly

- **Reports**: `/var/lib/guest-device-counter/reports/`
  - PDF reports generated on configured schedule
  - Named: `daily_report_YYYY-MM-DD.pdf`, etc.

- **Logs**: `/var/log/guest-device-counter/`
  - Application logs and debug information

## Database Schema

### Devices Table
Tracks all discovered devices with:
- MAC address (unique)
- IP address (current)
- Hostname
- Vendor
- Device type (detected)
- First/last seen timestamps
- Employee flag
- Employee flagged date

### Connection Log
Records every connection event:
- MAC address
- IP address
- Hostname
- Event time
- Event type (connected, disconnected)
- Status

### Daily Presence
Tracks days each device was seen for employee detection.

### Employee Detection
Maintains streak tracking for consecutive day detection.

## Report Contents

Each PDF report includes:

1. **Summary Statistics**
   - Total unique devices
   - Guest vs. employee device counts
   - Peak connection day and count
   - Date range

2. **Active Devices Table**
   - MAC address
   - IP address
   - Hostname
   - Vendor
   - Device type (iPhone, Android, Windows, etc.)

3. **Connection Events Log**
   - Timestamp
   - MAC address
   - IP address
   - Event type
   - Status

4. **Professional Formatting**
   - Venue branding
   - Clear headers and sections
   - Color-coded tables
   - Generation timestamp

## Network Setup

### VLAN Configuration

Ensure the Raspberry Pi is connected to the guest network VLAN:

```bash
# View network interfaces
ip link show

# Check IP configuration
ip addr show

# Verify network connectivity
ping 8.8.8.8
```

### DHCP Server Configuration

For best results with hostname detection, ensure dnsmasq is running:

```bash
# Install if needed
sudo apt-get install dnsmasq

# Check lease file location
sudo tail /var/lib/dnsmasq/dnsmasq.leases
```

## Troubleshooting

### Check Service Status
```bash
sudo systemctl status guest-device-counter
sudo journalctl -u guest-device-counter -n 50
```

### No Devices Detected
1. Verify network interface: `ip link show`
2. Check ARP scan: `sudo arp-scan --localnet`
3. Verify DHCP leases: `sudo cat /var/lib/dnsmasq/dnsmasq.leases`

### Permission Issues
```bash
sudo chown -R guest-device-counter:guest-device-counter /var/lib/guest-device-counter
sudo chmod 750 /var/lib/guest-device-counter
```

### Database Issues
```bash
# Check database integrity
sudo sqlite3 /var/lib/guest-device-counter/devices.db ".tables"

# Backup before troubleshooting
sudo cp /var/lib/guest-device-counter/devices.db /var/lib/guest-device-counter/devices.db.backup
```

## Performance Considerations

- **Scan Interval**: 15 minutes is recommended. Shorter intervals (5-10 min) use more CPU.
- **Database Size**: Grows ~100KB per 10,000 events. Monthly cleanup recommended.
- **Memory**: Typically uses 50-100MB with default settings.
- **CPU**: Runs on single core, ~5-10% during scans.

### Database Cleanup

```bash
# Purge events older than 90 days
sqlite3 /var/lib/guest-device-counter/devices.db << EOF
DELETE FROM connection_log 
WHERE event_time < datetime('now', '-90 days');
VACUUM;
EOF
```

## API / Direct Database Access

Query the SQLite database directly:

```bash
# List all guest devices
sqlite3 /var/lib/guest-device-counter/devices.db << EOF
SELECT mac_address, ip_address, hostname, device_type, last_seen
FROM devices
WHERE is_employee = 0
ORDER BY last_seen DESC;
EOF

# Export to CSV
sqlite3 -header -csv /var/lib/guest-device-counter/devices.db \
  "SELECT * FROM devices WHERE is_employee = 0" > guest_devices.csv
```

## Security Considerations

⚠️ **Important**
- The service has access to all network traffic information
- Run on isolated guest network only
- Restrict file access: `sudo chmod 750 /var/lib/guest-device-counter`
- Protect reports with appropriate access controls
- Consider encrypting database backups

## Maintenance

### Weekly
```bash
sudo systemctl status guest-device-counter
sudo journalctl -u guest-device-counter -n 100
```

### Monthly
```bash
# Backup database
sudo cp /var/lib/guest-device-counter/devices.db \
  /var/lib/guest-device-counter/devices.db.$(date +%Y-%m-%d).backup

# Cleanup old logs
sudo find /var/log/guest-device-counter -name "*.log" -mtime +30 -delete
```

## Uninstallation

```bash
sudo systemctl stop guest-device-counter
sudo systemctl disable guest-device-counter
sudo rm /etc/systemd/system/guest-device-counter.service
sudo systemctl daemon-reload
sudo pip3 uninstall guest-device-counter -y
```

## Contributing

Issues and pull requests welcome! Please ensure:
- Code follows PEP 8 style guidelines
- All tests pass
- Documentation is updated
- Commit messages are descriptive

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or feature requests, please open an issue on GitHub:
https://github.com/burfeindmark/GuestDeviceCount/issues

---

**Developed by Mark Burfeind**

