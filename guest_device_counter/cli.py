#!/usr/bin/env python3
"""
CLI tool for querying and managing Guest Device Counter data.
"""
import sqlite3
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from tabulate import tabulate


class DeviceDataCLI:
    """Command-line interface for device data queries."""

    def __init__(self, db_path: str = "/var/lib/guest-device-counter/devices.db"):
        self.db_path = db_path
        if not Path(db_path).exists():
            print(f"Error: Database not found at {db_path}", file=sys.stderr)
            sys.exit(1)

    def list_guest_devices(self, limit: int = 50):
        """List all active guest devices."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT mac_address, ip_address, hostname, vendor, device_type, last_seen
            FROM devices
            WHERE is_employee = 0
            ORDER BY last_seen DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        headers = ['MAC Address', 'IP Address', 'Hostname', 'Vendor', 'Device Type', 'Last Seen']
        print(tabulate(rows, headers=headers, tablefmt='grid'))
        conn.close()

    def list_employee_devices(self, limit: int = 50):
        """List all employee devices."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT mac_address, ip_address, hostname, vendor, device_type, employee_flagged_date
            FROM devices
            WHERE is_employee = 1
            ORDER BY employee_flagged_date DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        headers = ['MAC Address', 'IP Address', 'Hostname', 'Vendor', 'Device Type', 'Flagged Date']
        print(tabulate(rows, headers=headers, tablefmt='grid'))
        conn.close()

    def stats(self, days: int = 1):
        """Show statistics for the last N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT COUNT(DISTINCT mac_address) FROM connection_log
            WHERE DATE(event_time) >= ? AND DATE(event_time) <= ?
        """, (start_date, end_date))
        total_devices = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT cl.mac_address) FROM connection_log cl
            JOIN devices d ON cl.mac_address = d.mac_address
            WHERE d.is_employee = 0
            AND DATE(cl.event_time) >= ? AND DATE(cl.event_time) <= ?
        """, (start_date, end_date))
        guest_devices = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM connection_log
            WHERE DATE(event_time) >= ? AND DATE(event_time) <= ?
        """, (start_date, end_date))
        total_events = cursor.fetchone()[0]

        conn.close()

        stats_data = [
            ['Metric', 'Value'],
            ['Period', f'{start_date} to {end_date}'],
            ['Total Unique Devices', total_devices],
            ['Guest Devices', guest_devices],
            ['Employee Devices', total_devices - guest_devices],
            ['Total Connection Events', total_events],
        ]

        print(tabulate(stats_data, headers='firstrow', tablefmt='grid'))

    def device_history(self, mac_address: str, limit: int = 20):
        """Show connection history for a specific device."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # First, show device info
        cursor.execute("""
            SELECT mac_address, ip_address, hostname, vendor, device_type, first_seen, last_seen, is_employee
            FROM devices
            WHERE mac_address = ?
        """, (mac_address.lower(),))

        device = cursor.fetchone()
        if not device:
            print(f"Device not found: {mac_address}")
            conn.close()
            return

        print(f"\nDevice Information:")
        print(f"  MAC Address:     {device[0]}")
        print(f"  IP Address:      {device[1]}")
        print(f"  Hostname:        {device[2]}")
        print(f"  Vendor:          {device[3]}")
        print(f"  Device Type:     {device[4]}")
        print(f"  First Seen:      {device[5]}")
        print(f"  Last Seen:       {device[6]}")
        print(f"  Employee:        {'Yes' if device[7] else 'No'}")

        # Show connection events
        cursor.execute("""
            SELECT event_time, event_type, ip_address, status
            FROM connection_log
            WHERE mac_address = ?
            ORDER BY event_time DESC
            LIMIT ?
        """, (mac_address.lower(), limit))

        rows = cursor.fetchall()
        headers = ['Time', 'Event Type', 'IP Address', 'Status']
        print(f"\nRecent Events (last {limit}):")
        print(tabulate(rows, headers=headers, tablefmt='grid'))

        conn.close()

    def export_csv(self, output_file: str, is_employee: bool = False):
        """Export devices to CSV."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        emp_filter = "WHERE is_employee = 1" if is_employee else "WHERE is_employee = 0"

        cursor.execute(f"""
            SELECT mac_address, ip_address, hostname, vendor, device_type, first_seen, last_seen
            FROM devices
            {emp_filter}
            ORDER BY last_seen DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        # Write CSV
        with open(output_file, 'w') as f:
            f.write("MAC Address,IP Address,Hostname,Vendor,Device Type,First Seen,Last Seen\n")
            for row in rows:
                f.write(','.join(str(x) if x else '' for x in row) + '\n')

        print(f"Exported {len(rows)} devices to {output_file}")

    def cleanup_old_logs(self, days: int = 90):
        """Clean up connection logs older than N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM connection_log
            WHERE event_time < datetime('now', '-' || ? || ' days')
        """, (days,))

        count_before = cursor.fetchone()[0]

        cursor.execute("""
            DELETE FROM connection_log
            WHERE event_time < datetime('now', '-' || ? || ' days')
        """, (days,))

        cursor.execute("VACUUM")

        conn.commit()
        conn.close()

        print(f"Deleted {count_before} log entries older than {days} days")
        print("Database vacuumed")


def main():
    parser = argparse.ArgumentParser(
        description='Guest Device Counter CLI - Query and manage device data'
    )
    parser.add_argument('--db', default='/var/lib/guest-device-counter/devices.db',
                       help='Path to devices database')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Guest devices
    guest_parser = subparsers.add_parser('guests', help='List guest devices')
    guest_parser.add_argument('--limit', type=int, default=50, help='Number of devices to show')

    # Employee devices
    emp_parser = subparsers.add_parser('employees', help='List employee devices')
    emp_parser.add_argument('--limit', type=int, default=50, help='Number of devices to show')

    # Statistics
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--days', type=int, default=1, help='Number of days to analyze')

    # Device history
    hist_parser = subparsers.add_parser('history', help='Show device connection history')
    hist_parser.add_argument('mac', help='MAC address to look up')
    hist_parser.add_argument('--limit', type=int, default=20, help='Number of events to show')

    # Export
    export_parser = subparsers.add_parser('export', help='Export devices to CSV')
    export_parser.add_argument('output', help='Output CSV file')
    export_parser.add_argument('--employees', action='store_true', help='Export employee devices instead of guests')

    # Cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old logs')
    cleanup_parser.add_argument('--days', type=int, default=90, help='Keep logs newer than N days')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cli = DeviceDataCLI(args.db)

    if args.command == 'guests':
        cli.list_guest_devices(args.limit)
    elif args.command == 'employees':
        cli.list_employee_devices(args.limit)
    elif args.command == 'stats':
        cli.stats(args.days)
    elif args.command == 'history':
        cli.device_history(args.mac, args.limit)
    elif args.command == 'export':
        cli.export_csv(args.output, args.employees)
    elif args.command == 'cleanup':
        cli.cleanup_old_logs(args.days)


if __name__ == '__main__':
    main()
