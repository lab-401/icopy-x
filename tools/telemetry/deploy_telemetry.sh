#!/bin/bash
# Deploy all 3 telemetry layers to the iCopy-X device.
# Usage: bash tools/telemetry/deploy_telemetry.sh
set -e

SSH="sshpass -p fa ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p 2222 root@127.0.0.1"
SCP="sshpass -p fa scp -o StrictHostKeyChecking=no -P 2222"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Layer 1: System monitor ==="
$SCP "$DIR/sysmon.sh" root@127.0.0.1:/mnt/upan/sysmon.sh
$SSH 'chmod +x /mnt/upan/sysmon.sh'

# Create systemd unit
$SSH 'cat > /etc/systemd/system/sysmon.service << EOF
[Unit]
Description=System health monitor
After=local-fs.target

[Service]
Type=simple
ExecStart=/bin/bash /mnt/upan/sysmon.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable sysmon.service
systemctl start sysmon.service'
echo "  sysmon.service started"

echo "=== Layer 2: Python app telemetry ==="
$SCP "$DIR/app_trace.py" root@127.0.0.1:/usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py
echo "  sitecustomize.py deployed"

echo "=== Layer 3: Persistent journal (2MB cap) ==="
$SSH '
mkdir -p /var/log/journal
sed -i "s/^#Storage=.*/Storage=persistent/" /etc/systemd/journald.conf
sed -i "s/^Storage=.*/Storage=persistent/" /etc/systemd/journald.conf
# Add size limits if not present
grep -q "SystemMaxUse" /etc/systemd/journald.conf || echo "SystemMaxUse=2M" >> /etc/systemd/journald.conf
grep -q "RuntimeMaxUse" /etc/systemd/journald.conf || echo "RuntimeMaxUse=2M" >> /etc/systemd/journald.conf
systemctl restart systemd-journald'
echo "  persistent journal enabled (2MB cap)"

echo "=== Clear old logs ==="
$SSH 'rm -f /mnt/upan/sysmon.log /mnt/upan/app_trace.log /mnt/upan/crash_trace.log'

echo "=== Restart app to load sitecustomize ==="
$SSH 'kill $(pgrep -f "python3 /home/pi/ipk_app_main/app.py" | head -1) 2>/dev/null || true'
echo "  app restarted"

echo "=== Verify ==="
sleep 10
$SSH '
echo "sysmon: $(systemctl is-active sysmon.service)"
echo "sysmon log: $(wc -l < /mnt/upan/sysmon.log 2>/dev/null || echo missing) lines"
echo "app_trace: $(wc -l < /mnt/upan/app_trace.log 2>/dev/null || echo missing) lines"
echo "journal: $(ls /var/log/journal/ 2>/dev/null | wc -l) dirs"
'

echo "=== DONE — telemetry is live ==="
