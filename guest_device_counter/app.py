"""
Main application for Guest Device Counter service.
Orchestrates scanning, tracking, and reporting.
"""
import logging
import logging.handlers
import sys
import yaml
import schedule
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from guest_device_counter.database import DeviceDatabase
from guest_device_counter.scanner import NetworkScanner
from guest_device_counter.report import PDFReportGenerator


class GuestDeviceCounter:
    """Main service application for tracking guest network devices."""

    def __init__(self, config_path: str = '/etc/guest-device-counter/config.yml'):
        """Initialize the service."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.db = DeviceDatabase(self.config.get('database_path', 
                                                 '/var/lib/guest-device-counter/devices.db'))
        self.scanner = NetworkScanner(
            interface=self.config.get('network_interface'),
            network=self.config.get('network_range')
        )
        self.reporter = PDFReportGenerator(
            venue_name=self.config.get('venue_name', 'Guest Network'),
            output_dir=self.config.get('reports_dir', '/var/lib/guest-device-counter/reports')
        )
        
        self.logger.info("Guest Device Counter initialized")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        default_config = {
            'scan_interval_minutes': 15,
            'employee_threshold_days': 5,
            'venue_name': 'Guest Network',
            'network_interface': None,
            'network_range': None,
            'database_path': '/var/lib/guest-device-counter/devices.db',
            'reports_dir': '/var/lib/guest-device-counter/reports',
            'log_level': 'INFO',
            'enable_daily_reports': True,
            'enable_weekly_reports': True,
            'enable_monthly_reports': True,
            'daily_report_time': '09:00',
            'weekly_report_day': 0,  # Monday=0, Sunday=6
            'weekly_report_time': '09:00',
            'monthly_report_day': 1,
            'monthly_report_time': '09:00'
        }

        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    user_config = yaml.safe_load(f) or {}
                    default_config.update(user_config)
                    return default_config
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}", file=sys.stderr)

        return default_config

    def _setup_logging(self):
        """Set up logging to both console and syslog."""
        log_level = getattr(logging, self.config.get('log_level', 'INFO'))
        
        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)

        # Syslog handler (for systemd)
        try:
            syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
            syslog_handler.setLevel(log_level)
            syslog_format = logging.Formatter(
                'guest-device-counter[%(process)d]: %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_format)
            root_logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"Warning: Could not set up syslog handler: {e}", file=sys.stderr)

    def run_scan(self):
        """Execute a network scan and process results."""
        self.logger.info("Starting network scan")
        
        try:
            devices = self.scanner.get_active_devices()
            self.logger.info(f"Found {len(devices)} devices on network")

            for device in devices:
                mac = device['mac']
                
                # Add or update device in database
                self.db.add_or_update_device(
                    mac=mac,
                    ip=device.get('ip'),
                    hostname=device.get('hostname'),
                    vendor=device.get('vendor'),
                    device_type=device.get('device_type')
                )

                # Log the connection event
                self.db.log_connection(
                    mac=mac,
                    ip=device.get('ip'),
                    hostname=device.get('hostname'),
                    event_type='connected',
                    status='active'
                )

                # Record daily presence
                self.db.record_daily_presence(mac)

                # Check if device should be marked as employee
                if self.db.check_and_mark_employee(mac, self.config.get('employee_threshold_days', 5)):
                    self.logger.info(f"Device {mac} marked as employee after 5+ days")

            self.logger.info("Network scan completed successfully")

        except Exception as e:
            self.logger.error(f"Error during network scan: {e}", exc_info=True)

    def generate_daily_report(self):
        """Generate a daily report."""
        self.logger.info("Generating daily report")
        
        try:
            report_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            stats = self.db.get_stats(report_date, report_date)
            logs = self.db.get_connection_log(report_date, report_date)
            guest_devices = self.db.get_active_guest_devices(hours=24)

            report_path = self.reporter.generate_daily_report(stats, logs, guest_devices, report_date)
            self.logger.info(f"Daily report generated: {report_path}")

        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}", exc_info=True)

    def generate_weekly_report(self):
        """Generate a weekly report."""
        self.logger.info("Generating weekly report")
        
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            report_path = self.reporter.generate_weekly_report(self.db, start_date, end_date)
            self.logger.info(f"Weekly report generated: {report_path}")

        except Exception as e:
            self.logger.error(f"Error generating weekly report: {e}", exc_info=True)

    def generate_monthly_report(self):
        """Generate a monthly report."""
        self.logger.info("Generating monthly report")
        
        try:
            now = datetime.now()
            report_path = self.reporter.generate_monthly_report(self.db, now.year, now.month)
            self.logger.info(f"Monthly report generated: {report_path}")

        except Exception as e:
            self.logger.error(f"Error generating monthly report: {e}", exc_info=True)

    def schedule_tasks(self):
        """Schedule recurring tasks."""
        scan_interval = self.config.get('scan_interval_minutes', 15)
        
        # Scan at regular intervals
        schedule.every(scan_interval).minutes.do(self.run_scan)
        self.logger.info(f"Scheduled network scan every {scan_interval} minutes")

        # Daily report
        if self.config.get('enable_daily_reports'):
            daily_time = self.config.get('daily_report_time', '09:00')
            schedule.every().day.at(daily_time).do(self.generate_daily_report)
            self.logger.info(f"Scheduled daily report at {daily_time}")

        # Weekly report
        if self.config.get('enable_weekly_reports'):
            weekly_time = self.config.get('weekly_report_time', '09:00')
            weekly_day = self.config.get('weekly_report_day', 0)
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            getattr(schedule.every(), days[weekly_day]).at(weekly_time).do(self.generate_weekly_report)
            self.logger.info(f"Scheduled weekly report every {days[weekly_day]} at {weekly_time}")

        # Monthly report
        if self.config.get('enable_monthly_reports'):
            monthly_time = self.config.get('monthly_report_time', '09:00')
            schedule.every().month.at(monthly_time).do(self.generate_monthly_report)
            self.logger.info(f"Scheduled monthly report at {monthly_time}")

        # Run first scan immediately
        self.run_scan()

    def run(self):
        """Run the service main loop."""
        self.logger.info("Starting Guest Device Counter service")
        self.schedule_tasks()

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check schedule every minute
        except KeyboardInterrupt:
            self.logger.info("Service shutting down")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Guest Device Counter Service')
    parser.add_argument('-c', '--config', default='/etc/guest-device-counter/config.yml',
                       help='Path to configuration file')
    parser.add_argument('--scan', action='store_true', help='Run a single scan and exit')
    parser.add_argument('--daily-report', action='store_true', help='Generate daily report and exit')
    parser.add_argument('--weekly-report', action='store_true', help='Generate weekly report and exit')
    parser.add_argument('--monthly-report', action='store_true', help='Generate monthly report and exit')
    
    args = parser.parse_args()

    app = GuestDeviceCounter(args.config)

    if args.scan:
        app.run_scan()
    elif args.daily_report:
        app.generate_daily_report()
    elif args.weekly_report:
        app.generate_weekly_report()
    elif args.monthly_report:
        app.generate_monthly_report()
    else:
        app.run()


if __name__ == '__main__':
    main()
