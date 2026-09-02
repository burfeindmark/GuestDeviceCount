"""
Network scanner module for discovering devices on the guest network.
Uses ARP and DHCP scanning for device discovery.
"""
import subprocess
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime


class NetworkScanner:
    """Scan the guest network for connected devices."""

    def __init__(self, interface: str = None, network: str = None):
        """
        Initialize the scanner.
        
        Args:
            interface: Network interface to scan (e.g., 'eth0')
            network: CIDR network to scan (e.g., '192.168.100.0/24')
        """
        self.interface = interface
        self.network = network
        self.logger = logging.getLogger(__name__)

    def scan_arp(self) -> List[Dict]:
        """
        Scan using ARP for currently connected devices.
        Returns list of connected devices with MAC, IP, hostname info.
        """
        devices = []
        
        try:
            # Use arp-scan or arp command to discover devices
            if self.network:
                cmd = ['arp-scan', '--localnet']
                if self.interface:
                    cmd.extend(['-I', self.interface])
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            else:
                cmd = ['arp', '-a']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                devices = self._parse_arp_output(result.stdout)
            else:
                self.logger.warning(f"ARP scan failed: {result.stderr}")
                # Fallback to parsing /proc/net/arp on Linux
                devices = self._parse_proc_arp()

        except FileNotFoundError:
            self.logger.info("arp-scan not found, using /proc/net/arp fallback")
            devices = self._parse_proc_arp()
        except subprocess.TimeoutExpired:
            self.logger.error("ARP scan timed out")
        except Exception as e:
            self.logger.error(f"Error during ARP scan: {e}")

        return devices

    def _parse_arp_output(self, output: str) -> List[Dict]:
        """Parse arp-scan or arp output."""
        devices = []
        
        for line in output.split('\n'):
            line = line.strip()
            if not line or line.startswith('Interface'):
                continue

            # Parse arp-scan format: IP<TAB>MAC<TAB>Vendor
            parts = line.split('\t')
            if len(parts) >= 2:
                ip = parts[0].strip()
                mac = parts[1].strip()
                vendor = parts[2].strip() if len(parts) > 2 else None

                if self._is_valid_mac(mac):
                    devices.append({
                        'mac': mac.lower(),
                        'ip': ip,
                        'vendor': vendor,
                        'hostname': None,
                        'device_type': self._guess_device_type(vendor)
                    })

        return devices

    def _parse_proc_arp(self) -> List[Dict]:
        """Parse Linux /proc/net/arp file."""
        devices = []
        
        try:
            with open('/proc/net/arp', 'r') as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[0]
                        mac = parts[3]
                        
                        if mac != '00:00:00:00:00:00' and self._is_valid_mac(mac):
                            devices.append({
                                'mac': mac.lower(),
                                'ip': ip,
                                'vendor': None,
                                'hostname': None,
                                'device_type': None
                            })
        except FileNotFoundError:
            self.logger.error("/proc/net/arp not found")
        except Exception as e:
            self.logger.error(f"Error parsing /proc/net/arp: {e}")

        return devices

    def scan_dhcp_leases(self) -> List[Dict]:
        """
        Scan DHCP leases from dnsmasq or ISC dhcp server.
        Returns list of devices with leases.
        """
        devices = []
        
        try:
            # Try dnsmasq leases first (common on Raspberry Pi)
            devices.extend(self._parse_dnsmasq_leases())
        except Exception as e:
            self.logger.warning(f"Error parsing dnsmasq leases: {e}")

        try:
            # Try ISC dhcpd leases
            devices.extend(self._parse_dhcpd_leases())
        except Exception as e:
            self.logger.warning(f"Error parsing dhcpd leases: {e}")

        return devices

    def _parse_dnsmasq_leases(self) -> List[Dict]:
        """Parse dnsmasq lease file."""
        devices = []
        dhcp_leases_paths = [
            '/var/lib/dnsmasq/dnsmasq.leases',
            '/var/lib/misc/dnsmasq.leases',
            '/var/cache/dnsmasq/leases.txt'
        ]

        for lease_file in dhcp_leases_paths:
            try:
                with open(lease_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            mac = parts[1]
                            ip = parts[2]
                            hostname = parts[3] if parts[3] != '*' else None

                            if self._is_valid_mac(mac):
                                devices.append({
                                    'mac': mac.lower(),
                                    'ip': ip,
                                    'hostname': hostname,
                                    'vendor': None,
                                    'device_type': self._guess_device_type(hostname)
                                })
                break
            except FileNotFoundError:
                continue

        return devices

    def _parse_dhcpd_leases(self) -> List[Dict]:
        """Parse ISC dhcpd lease file."""
        devices = []
        lease_files = [
            '/var/lib/dhcp/dhcpd.leases',
            '/var/lib/dhcpd.leases'
        ]

        for lease_file in lease_files:
            try:
                with open(lease_file, 'r') as f:
                    content = f.read()
                    # Parse lease blocks
                    lease_pattern = r'lease\s+([\d.]+)\s*\{([^}]+)\}'
                    for match in re.finditer(lease_pattern, content):
                        ip = match.group(1)
                        lease_block = match.group(2)

                        # Extract hardware address
                        hw_match = re.search(r'hardware\s+ethernet\s+([\da-f:]+)', lease_block)
                        if hw_match:
                            mac = hw_match.group(1)
                            
                            # Extract hostname
                            hostname = None
                            hostname_match = re.search(r'client-hostname\s+"([^"]+)"', lease_block)
                            if hostname_match:
                                hostname = hostname_match.group(1)

                            if self._is_valid_mac(mac):
                                devices.append({
                                    'mac': mac.lower(),
                                    'ip': ip,
                                    'hostname': hostname,
                                    'vendor': None,
                                    'device_type': self._guess_device_type(hostname)
                                })
                break
            except FileNotFoundError:
                continue

        return devices

    def reverse_dns_lookup(self, ip: str) -> Optional[str]:
        """Attempt reverse DNS lookup for an IP address."""
        try:
            result = subprocess.run(
                ['dig', '+short', '-x', ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                hostname = result.stdout.strip().rstrip('.')
                if hostname:
                    return hostname
        except Exception as e:
            self.logger.debug(f"Reverse DNS lookup failed for {ip}: {e}")

        return None

    @staticmethod
    def _is_valid_mac(mac: str) -> bool:
        """Validate MAC address format."""
        mac_pattern = r'^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$'
        return bool(re.match(mac_pattern, mac))

    @staticmethod
    def _guess_device_type(vendor_or_hostname: str) -> Optional[str]:
        """Guess device type from vendor or hostname."""
        if not vendor_or_hostname:
            return None

        vendor_lower = vendor_or_hostname.lower()
        
        if any(x in vendor_lower for x in ['apple', 'iphone', 'ipad', 'mac']):
            return 'Apple'
        elif any(x in vendor_lower for x in ['android', 'samsung', 'pixel', 'xiaomi']):
            return 'Android'
        elif any(x in vendor_lower for x in ['printer', 'canon', 'xerox']):
            return 'Printer'
        elif any(x in vendor_lower for x in ['windows', 'microsoft', 'dell', 'lenovo']):
            return 'Windows'
        elif any(x in vendor_lower for x in ['linux', 'ubuntu', 'debian', 'raspberry']):
            return 'Linux'
        elif any(x in vendor_lower for x in ['tv', 'lg', 'roku', 'fire']):
            return 'Smart TV'
        elif any(x in vendor_lower for x in ['iot', 'smart', 'camera', 'sensor']):
            return 'IoT Device'

        return None

    def get_active_devices(self) -> List[Dict]:
        """Get all active devices on the network."""
        devices_arp = self.scan_arp()
        devices_dhcp = self.scan_dhcp_leases()

        # Merge, preferring DHCP data (has hostname info)
        devices_dict = {}
        
        for device in devices_arp:
            devices_dict[device['mac']] = device

        for device in devices_dhcp:
            if device['mac'] in devices_dict:
                devices_dict[device['mac']].update(device)
            else:
                devices_dict[device['mac']] = device

        return list(devices_dict.values())
