"""
PDF report generator for device statistics and analytics.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import logging

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


class PDFReportGenerator:
    """Generate PDF reports from device data."""

    def __init__(self, venue_name: str = "Guest Network", output_dir: str = None):
        """
        Initialize the PDF generator.
        
        Args:
            venue_name: Name of the venue for the report
            output_dir: Directory to save PDF reports
        """
        self.venue_name = venue_name
        self.output_dir = Path(output_dir) if output_dir else Path('/var/lib/guest-device-counter/reports')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def generate_daily_report(self, stats: Dict, connection_log: List[Dict], 
                            guest_devices: List[Dict], report_date: str = None) -> str:
        """Generate a daily device report."""
        if report_date is None:
            report_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        filename = self.output_dir / f"daily_report_{report_date}.pdf"
        
        doc = SimpleDocTemplate(str(filename), pagesize=letter,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.75*inch, rightMargin=0.75*inch)
        
        story = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2e5c8a'),
            spaceAfter=10,
            spaceBefore=10
        )

        # Title
        story.append(Paragraph(f"Guest Network Device Report - {self.venue_name}", title_style))
        story.append(Paragraph(f"Report Date: {report_date}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # Summary Statistics
        story.append(Paragraph("Summary Statistics", heading_style))
        stats_data = [
            ['Metric', 'Count'],
            ['Total Unique Devices', str(stats.get('total_devices', 0))],
            ['Guest Devices', str(stats.get('guest_devices', 0))],
            ['Employee Devices (Filtered)', str(stats.get('employee_devices', 0))],
            ['Peak Connections Day', str(stats.get('peak_day', 'N/A'))],
            ['Peak Connection Count', str(stats.get('peak_connections', 0))],
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 0.3*inch))

        # Active Guest Devices
        story.append(Paragraph(f"Active Guest Devices ({len(guest_devices)})", heading_style))
        
        if guest_devices:
            device_data = [
                ['MAC Address', 'IP Address', 'Hostname', 'Vendor', 'Device Type']
            ]
            
            for device in guest_devices[:100]:  # Limit to first 100
                device_data.append([
                    device.get('mac', 'N/A')[:17],
                    device.get('ip', 'N/A'),
                    device.get('hostname', 'N/A') or 'Unknown',
                    device.get('vendor', 'N/A')[:30] if device.get('vendor') else 'Unknown',
                    device.get('device_type', 'Unknown') or 'Unknown'
                ])
            
            device_table = Table(device_data, colWidths=[1.3*inch, 1*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            device_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            story.append(device_table)
        else:
            story.append(Paragraph("No active guest devices detected.", styles['Normal']))

        story.append(Spacer(1, 0.2*inch))

        # Connection Log Summary
        story.append(PageBreak())
        story.append(Paragraph("Recent Connection Events", heading_style))
        
        if connection_log:
            log_data = [['Time', 'MAC Address', 'IP Address', 'Event Type', 'Status']]
            
            for log_entry in connection_log[:50]:  # Show last 50 entries
                log_data.append([
                    log_entry.get('event_time', 'N/A')[:19],
                    log_entry.get('mac', 'N/A')[:17],
                    log_entry.get('ip', 'N/A'),
                    log_entry.get('event_type', 'N/A'),
                    log_entry.get('status', 'N/A')
                ])
            
            log_table = Table(log_data, colWidths=[1.3*inch, 1.3*inch, 1*inch, 1*inch, 0.8*inch])
            log_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            story.append(log_table)
        else:
            story.append(Paragraph("No connection events recorded.", styles['Normal']))

        # Footer
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph(
            f"<i>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
            styles['Normal']
        ))

        doc.build(story)
        self.logger.info(f"Daily report generated: {filename}")
        return str(filename)

    def generate_weekly_report(self, db, start_date: str = None, end_date: str = None) -> str:
        """Generate a weekly summary report."""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        filename = self.output_dir / f"weekly_report_{start_date}_to_{end_date}.pdf"
        
        # Get data from database
        stats = db.get_stats(start_date, end_date)
        logs = db.get_connection_log(start_date, end_date)
        guest_devices = db.get_active_guest_devices(hours=168)  # 7 days

        return self._build_report(filename, "Weekly Report", start_date, end_date, 
                                 stats, logs, guest_devices)

    def generate_monthly_report(self, db, year: int = None, month: int = None) -> str:
        """Generate a monthly summary report."""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        # Calculate date range
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        start_date = first_day.strftime('%Y-%m-%d')
        end_date = last_day.strftime('%Y-%m-%d')
        
        filename = self.output_dir / f"monthly_report_{year}-{month:02d}.pdf"

        # Get data from database
        stats = db.get_stats(start_date, end_date)
        logs = db.get_connection_log(start_date, end_date)
        guest_devices = db.get_active_guest_devices(hours=730)  # ~30 days

        return self._build_report(filename, f"Monthly Report - {first_day.strftime('%B %Y')}", 
                                 start_date, end_date, stats, logs, guest_devices)

    def _build_report(self, filename: Path, report_title: str, start_date: str, end_date: str,
                     stats: Dict, logs: List[Dict], guest_devices: List[Dict]) -> str:
        """Build a generic report."""
        doc = SimpleDocTemplate(str(filename), pagesize=letter,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.75*inch, rightMargin=0.75*inch)
        
        story = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2e5c8a'),
            spaceAfter=10,
            spaceBefore=10
        )

        # Title
        story.append(Paragraph(f"{report_title} - {self.venue_name}", title_style))
        story.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # Statistics
        story.append(Paragraph("Summary Statistics", heading_style))
        stats_data = [
            ['Metric', 'Count'],
            ['Total Unique Devices', str(stats.get('total_devices', 0))],
            ['Guest Devices', str(stats.get('guest_devices', 0))],
            ['Employee Devices (Filtered)', str(stats.get('employee_devices', 0))],
            ['Peak Day', str(stats.get('peak_day', 'N/A'))],
            ['Peak Connections', str(stats.get('peak_connections', 0))],
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 0.2*inch))

        # Top Devices
        story.append(Paragraph(f"Active Devices ({len(guest_devices)})", heading_style))
        
        if guest_devices:
            device_data = [['MAC Address', 'IP Address', 'Hostname', 'Device Type']]
            for device in guest_devices[:50]:
                device_data.append([
                    device.get('mac', 'N/A')[:17],
                    device.get('ip', 'N/A'),
                    device.get('hostname', 'N/A') or 'Unknown',
                    device.get('device_type', 'Unknown') or 'Unknown'
                ])
            
            device_table = Table(device_data, colWidths=[1.5*inch, 1.2*inch, 1.8*inch, 1.5*inch])
            device_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            story.append(device_table)

        # Footer
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            f"<i>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
            styles['Normal']
        ))

        doc.build(story)
        self.logger.info(f"Report generated: {filename}")
        return str(filename)
