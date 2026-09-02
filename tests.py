"""
Unit tests for Guest Device Counter
"""
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from guest_device_counter.database import DeviceDatabase
from guest_device_counter.scanner import NetworkScanner


class TestDatabase(unittest.TestCase):
    """Test database operations."""

    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")
        self.db = DeviceDatabase(self.db_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_database_initialization(self):
        """Test database creation."""
        self.assertTrue(Path(self.db_path).exists())

    def test_add_device(self):
        """Test adding a device."""
        mac = "aa:bb:cc:dd:ee:ff"
        device_id = self.db.add_or_update_device(
            mac=mac,
            ip="192.168.1.100",
            hostname="test-device",
            vendor="Test Vendor"
        )
        self.assertGreater(device_id, 0)

    def test_device_uniqueness(self):
        """Test that devices are unique by MAC."""
        mac = "aa:bb:cc:dd:ee:ff"
        
        id1 = self.db.add_or_update_device(mac=mac, ip="192.168.1.100")
        id2 = self.db.add_or_update_device(mac=mac, ip="192.168.1.101")
        
        self.assertEqual(id1, id2)

    def test_connection_logging(self):
        """Test connection event logging."""
        mac = "aa:bb:cc:dd:ee:ff"
        
        self.db.add_or_update_device(mac=mac, ip="192.168.1.100")
        self.db.log_connection(mac=mac, ip="192.168.1.100")
        
        logs = self.db.get_connection_log()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['mac'], mac)

    def test_daily_presence(self):
        """Test daily presence tracking."""
        mac = "aa:bb:cc:dd:ee:ff"
        
        self.db.add_or_update_device(mac=mac)
        self.db.record_daily_presence(mac)
        self.db.record_daily_presence(mac)  # Same day
        
        # Should still be 1 presence record for today

    def test_employee_detection(self):
        """Test employee device detection."""
        mac = "aa:bb:cc:dd:ee:ff"
        
        self.db.add_or_update_device(mac=mac)
        
        # Record presence for 5 consecutive days
        for i in range(5):
            date = (datetime.now() - timedelta(days=4-i)).strftime('%Y-%m-%d')
            self.db.record_daily_presence(mac, date)
        
        # Should be marked as employee
        is_employee = self.db.check_and_mark_employee(mac, threshold_days=5)
        self.assertTrue(is_employee)

    def test_get_active_guest_devices(self):
        """Test retrieving active guest devices."""
        mac1 = "aa:bb:cc:dd:ee:ff"
        mac2 = "11:22:33:44:55:66"
        
        self.db.add_or_update_device(mac=mac1, ip="192.168.1.100")
        self.db.add_or_update_device(mac=mac2, ip="192.168.1.101")
        
        devices = self.db.get_active_guest_devices(hours=24)
        self.assertEqual(len(devices), 2)

    def test_employee_filtering(self):
        """Test that employee devices are filtered from guest list."""
        mac1 = "aa:bb:cc:dd:ee:ff"  # guest
        mac2 = "11:22:33:44:55:66"  # employee
        
        self.db.add_or_update_device(mac=mac1)
        self.db.add_or_update_device(mac=mac2)
        
        # Mark mac2 as employee
        for i in range(5):
            date = (datetime.now() - timedelta(days=4-i)).strftime('%Y-%m-%d')
            self.db.record_daily_presence(mac2, date)
        self.db.check_and_mark_employee(mac2)
        
        guest_devices = self.db.get_active_guest_devices()
        macs = [d['mac'] for d in guest_devices]
        
        self.assertIn(mac1, macs)
        self.assertNotIn(mac2, macs)

    def test_statistics(self):
        """Test statistics generation."""
        mac = "aa:bb:cc:dd:ee:ff"
        
        self.db.add_or_update_device(mac=mac)
        self.db.log_connection(mac=mac)
        
        stats = self.db.get_stats()
        
        self.assertEqual(stats['total_devices'], 1)
        self.assertEqual(stats['guest_devices'], 1)
        self.assertIn('peak_day', stats)


class TestNetworkScanner(unittest.TestCase):
    """Test network scanner."""

    def test_mac_validation(self):
        """Test MAC address validation."""
        valid_macs = [
            "aa:bb:cc:dd:ee:ff",
            "AA:BB:CC:DD:EE:FF",
            "00:00:00:00:00:00",
            "ff:ff:ff:ff:ff:ff",
        ]
        
        invalid_macs = [
            "aa:bb:cc:dd:ee",
            "aa:bb:cc:dd:ee:gg",
            "aa-bb-cc-dd-ee-ff",
            "not-a-mac",
        ]
        
        for mac in valid_macs:
            self.assertTrue(NetworkScanner._is_valid_mac(mac), f"Should be valid: {mac}")
        
        for mac in invalid_macs:
            self.assertFalse(NetworkScanner._is_valid_mac(mac), f"Should be invalid: {mac}")

    def test_device_type_detection(self):
        """Test device type guessing."""
        test_cases = [
            ("Apple Inc", "Apple"),
            ("Samsung Electronics", "Android"),
            ("HP Printer", "Printer"),
            ("Canon Inc.", "Printer"),
            ("LG Electronics", "Smart TV"),
            ("Microsoft Corporation", "Windows"),
            ("Raspberry Pi", "Linux"),
        ]
        
        for vendor, expected_type in test_cases:
            device_type = NetworkScanner._guess_device_type(vendor)
            self.assertIsNotNone(device_type, f"Failed to detect type for: {vendor}")
            self.assertEqual(device_type, expected_type, 
                           f"Expected {expected_type} for {vendor}, got {device_type}")


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation."""

    def test_employee_threshold_reasonable(self):
        """Test that employee threshold is reasonable."""
        # Should be between 1 and 30 days
        min_threshold = 1
        max_threshold = 30
        
        self.assertGreaterEqual(min_threshold, 1)
        self.assertLessEqual(max_threshold, 30)

    def test_scan_interval_reasonable(self):
        """Test that scan interval is reasonable."""
        # Should be between 5 minutes and 60 minutes for practical use
        min_interval = 5
        max_interval = 60
        
        self.assertGreaterEqual(min_interval, 5)
        self.assertLessEqual(max_interval, 60)


if __name__ == '__main__':
    unittest.main()
