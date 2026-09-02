# Multi-stage build for Guest Device Counter
FROM python:3.11-slim as builder

WORKDIR /build
COPY . .

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev && \
    pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    arp-scan \
    dnsmasq \
    net-tools \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create service user
RUN groupadd -r gdc && useradd -r -g gdc gdc

# Set working directory
WORKDIR /app

# Copy application and Python packages from builder
COPY --from=builder /build /app
COPY --from=builder /root/.local /root/.local

# Update PATH
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Create required directories
RUN mkdir -p /var/lib/guest-device-counter/reports \
    /var/log/guest-device-counter \
    /etc/guest-device-counter && \
    chown -R gdc:gdc /var/lib/guest-device-counter /var/log/guest-device-counter

# Copy config
COPY config.yml /etc/guest-device-counter/config.yml
RUN chown gdc:gdc /etc/guest-device-counter/config.yml

# Install package
RUN pip install --no-cache-dir -e .

# Create health check
HEALTHCHECK --interval=5m --timeout=30s --start-period=10s --retries=3 \
    CMD sqlite3 /var/lib/guest-device-counter/devices.db ".tables" > /dev/null 2>&1 || exit 1

# Run as gdc user
USER gdc

# Expose for debugging (optional)
EXPOSE 8000

# Run service
CMD ["python3", "-m", "guest_device_counter.app", "-c", "/etc/guest-device-counter/config.yml"]
