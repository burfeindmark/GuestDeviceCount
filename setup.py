#!/usr/bin/env python3
"""Setup script for Guest Device Counter."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="guest-device-counter",
    version="1.0.0",
    author="Mark Burfeind",
    description="Network device tracking and analytics for public venue guest networks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/burfeindmark/GuestDeviceCount",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Topic :: Internet :: Log Analysis",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.7",
    install_requires=[
        "scapy>=2.5.0",
        "netifaces>=0.11.0",
        "reportlab>=4.0.0",
        "PyYAML>=6.0",
        "python-dateutil>=2.8.0",
        "schedule>=1.1.0",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "guest-device-counter=guest_device_counter.app:main",
            "gdc-query=guest_device_counter.cli:main",
        ],
    },
)
