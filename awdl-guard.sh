#!/bin/bash
# awdl-guard.sh - Automatically disable AWDL when it reactivates (e.g., after sleep/wake)
# Run with: sudo ./awdl-guard.sh
# Or in background: sudo nohup ./awdl-guard.sh &

CHECK_INTERVAL=5  # seconds between checks

echo "AWDL Guard started - monitoring for AWDL reactivation..."
echo "Press Ctrl+C to stop"

while true; do
    status=$(ifconfig awdl0 2>/dev/null | grep -o "status: [a-z]*" | cut -d' ' -f2)

    if [ "$status" = "active" ]; then
        echo "$(date '+%H:%M:%S') - AWDL detected active, disabling..."
        ifconfig awdl0 down
        echo "$(date '+%H:%M:%S') - AWDL disabled"
    fi

    sleep $CHECK_INTERVAL
done
