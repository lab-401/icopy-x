#!/bin/bash
# System monitor — runs independently of the Python app.
# Writes periodic snapshots to /mnt/upan/sysmon.log.
# Deployed as systemd service: sysmon.service

LOG=/mnt/upan/sysmon.log

echo "=== BOOT $(date '+%Y-%m-%d %H:%M:%S') ===" >> $LOG

while true; do
    {
        echo "--- $(date '+%H:%M:%S') up=$(cat /proc/uptime | cut -d' ' -f1)s ---"

        # Load
        cat /proc/loadavg

        # Memory
        free -m | grep Mem

        # Process counts
        PY=$(pgrep -c python 2>/dev/null || echo 0)
        SSH=$(pgrep -c sshd 2>/dev/null || echo 0)
        PM3=$(pgrep -c proxmark 2>/dev/null || echo 0)
        THR=$(ls /proc/$(pgrep -f 'python.*app.py' -o | head -1)/task/ 2>/dev/null | wc -l)
        echo "procs: py=$PY ssh=$SSH pm3=$PM3 app_threads=$THR"

        # Devices
        echo -n "dev: "
        [ -e /dev/ttyS0 ] && echo -n "ttyS0 " || echo -n "NO_ttyS0 "
        [ -e /dev/ttyACM0 ] && echo -n "ttyACM0 " || echo -n "NO_ttyACM0 "
        echo ""

        # Disk
        df -h /mnt/upan 2>/dev/null | tail -1

        # Last 3 dmesg lines (new since boot)
        dmesg | tail -3

    } >> $LOG 2>&1

    sleep 30
done
