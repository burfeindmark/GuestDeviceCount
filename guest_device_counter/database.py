"""
Device database schema and operations for Guest Network Device Counter.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class DeviceDatabase:
    def __init__(self, db_path: str = "/var/lib/guest-device-counter/devices.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Devices table: tracks all discovered devices
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT UNIQUE NOT NULL,
                ip_address TEXT,
                hostname TEXT,
                vendor TEXT,
                first_seen TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                is_employee BOOLEAN DEFAULT 0,
                employee_flagged_date TIMESTAMP,
                device_type TEXT,
                notes TEXT
            )
        """)

        # Connection log: tracks every connection event
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL,
                ip_address TEXT,
                hostname TEXT,
                event_time TIMESTAMP NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT,
                FOREIGN KEY(mac_address) REFERENCES devices(mac_address)
            )
        """)

        # Daily presence: tracks days a device was seen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_presence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL,
                presence_date DATE NOT NULL,
                count INTEGER DEFAULT 1,
                FOREIGN KEY(mac_address) REFERENCES devices(mac_address),
                UNIQUE(mac_address, presence_date)
            )
        """)

        # Employee detection log: tracks consecutive days for employee detection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_detection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL,
                consecutive_days INTEGER DEFAULT 1,
                streak_start_date DATE NOT NULL,
                last_checked TIMESTAMP NOT NULL,
                FOREIGN KEY(mac_address) REFERENCES devices(mac_address)
            )
        """)

        # Create indices for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_employee ON devices(is_employee)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_mac ON connection_log(mac_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_time ON connection_log(event_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_presence_date ON daily_presence(presence_date)")

        conn.commit()
        conn.close()

    def add_or_update_device(self, mac: str, ip: str = None, hostname: str = None, 
                            vendor: str = None, device_type: str = None) -> int:
        """Add or update a device in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now()

        try:
            cursor.execute("""
                INSERT INTO devices (mac_address, ip_address, hostname, vendor, device_type, 
                                     first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (mac, ip, hostname, vendor, device_type, now, now))
            device_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # Device exists, update it
            cursor.execute("""
                UPDATE devices 
                SET ip_address = COALESCE(?, ip_address),
                    hostname = COALESCE(?, hostname),
                    vendor = COALESCE(?, vendor),
                    device_type = COALESCE(?, device_type),
                    last_seen = ?
                WHERE mac_address = ?
            """, (ip, hostname, vendor, device_type, now, mac))
            cursor.execute("SELECT id FROM devices WHERE mac_address = ?", (mac,))
            device_id = cursor.fetchone()[0]

        conn.commit()
        conn.close()
        return device_id

    def log_connection(self, mac: str, ip: str = None, hostname: str = None, 
                      event_type: str = "connected", status: str = "active"):
        """Log a device connection event."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now()

        cursor.execute("""
            INSERT INTO connection_log (mac_address, ip_address, hostname, event_time, 
                                       event_type, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (mac, ip, hostname, now, event_type, status))

        conn.commit()
        conn.close()

    def record_daily_presence(self, mac: str, presence_date: str = None):
        """Record that a device was present on a given date."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if presence_date is None:
            presence_date = datetime.now().date()

        try:
            cursor.execute("""
                INSERT INTO daily_presence (mac_address, presence_date, count)
                VALUES (?, ?, 1)
            """, (mac, presence_date))
        except sqlite3.IntegrityError:
            cursor.execute("""
                UPDATE daily_presence 
                SET count = count + 1
                WHERE mac_address = ? AND presence_date = ?
            """, (mac, presence_date))

        conn.commit()
        conn.close()

    def check_and_mark_employee(self, mac: str, threshold_days: int = 5) -> bool:
        """Check if a device should be marked as employee (seen for N consecutive days)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get the presence record for this device
        cursor.execute("""
            SELECT COUNT(*) FROM daily_presence
            WHERE mac_address = ?
            AND presence_date >= date('now', '-5 days')
        """, (mac,))
        
        consecutive_days = cursor.fetchone()[0]

        if consecutive_days >= threshold_days:
            cursor.execute("""
                UPDATE devices 
                SET is_employee = 1, employee_flagged_date = ?
                WHERE mac_address = ?
            """, (datetime.now(), mac))
            conn.commit()
            conn.close()
            return True

        conn.close()
        return False

    def get_active_guest_devices(self, hours: int = 24) -> List[Dict]:
        """Get all active guest devices from the last N hours."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=hours)

        cursor.execute("""
            SELECT DISTINCT d.id, d.mac_address, d.ip_address, d.hostname, d.vendor, 
                            d.device_type, d.first_seen, d.last_seen
            FROM devices d
            WHERE d.is_employee = 0
            AND d.last_seen > ?
            ORDER BY d.last_seen DESC
        """, (cutoff_time,))

        devices = []
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'mac': row[1],
                'ip': row[2],
                'hostname': row[3],
                'vendor': row[4],
                'device_type': row[5],
                'first_seen': row[6],
                'last_seen': row[7]
            })

        conn.close()
        return devices

    def get_all_employee_devices(self) -> List[Dict]:
        """Get all devices marked as employee."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, mac_address, ip_address, hostname, vendor, device_type, 
                   first_seen, employee_flagged_date
            FROM devices
            WHERE is_employee = 1
            ORDER BY employee_flagged_date DESC
        """)

        devices = []
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'mac': row[1],
                'ip': row[2],
                'hostname': row[3],
                'vendor': row[4],
                'device_type': row[5],
                'first_seen': row[6],
                'flagged_date': row[7]
            })

        conn.close()
        return devices

    def get_connection_log(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get connection logs for a date range."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=1)).date()
        if end_date is None:
            end_date = datetime.now().date()

        cursor.execute("""
            SELECT mac_address, ip_address, hostname, event_time, event_type, status
            FROM connection_log
            WHERE DATE(event_time) >= ? AND DATE(event_time) <= ?
            ORDER BY event_time DESC
        """, (start_date, end_date))

        logs = []
        for row in cursor.fetchall():
            logs.append({
                'mac': row[0],
                'ip': row[1],
                'hostname': row[2],
                'event_time': row[3],
                'event_type': row[4],
                'status': row[5]
            })

        conn.close()
        return logs

    def get_stats(self, start_date: str = None, end_date: str = None) -> Dict:
        """Get statistics for a date range."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=1)).date()
        if end_date is None:
            end_date = datetime.now().date()

        # Total unique devices seen
        cursor.execute("""
            SELECT COUNT(DISTINCT mac_address) FROM connection_log
            WHERE DATE(event_time) >= ? AND DATE(event_time) <= ?
        """, (start_date, end_date))
        total_devices = cursor.fetchone()[0]

        # Guest devices only
        cursor.execute("""
            SELECT COUNT(DISTINCT cl.mac_address) FROM connection_log cl
            JOIN devices d ON cl.mac_address = d.mac_address
            WHERE d.is_employee = 0
            AND DATE(cl.event_time) >= ? AND DATE(cl.event_time) <= ?
        """, (start_date, end_date))
        guest_devices = cursor.fetchone()[0]

        # Peak connections
        cursor.execute("""
            SELECT DATE(event_time) as day, COUNT(*) as connections
            FROM connection_log
            WHERE DATE(event_time) >= ? AND DATE(event_time) <= ?
            GROUP BY DATE(event_time)
            ORDER BY connections DESC
            LIMIT 1
        """, (start_date, end_date))
        peak_row = cursor.fetchone()
        peak_day = peak_row[0] if peak_row else None
        peak_count = peak_row[1] if peak_row else 0

        conn.close()
        return {
            'total_devices': total_devices,
            'guest_devices': guest_devices,
            'employee_devices': total_devices - guest_devices,
            'peak_day': peak_day,
            'peak_connections': peak_count,
            'start_date': str(start_date),
            'end_date': str(end_date)
        }
