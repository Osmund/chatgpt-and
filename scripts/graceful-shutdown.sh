#!/bin/bash
# Graceful shutdown script for Anda
# Stops all services properly before system shutdown

echo "🛑 Starting graceful shutdown of Anda..."

# First, take a backup of the database
echo "  💾 Taking backup of database..."
if [ -f /home/admog/Code/chatgpt-and/backup-anda.sh ]; then
    bash /home/admog/Code/chatgpt-and/backup-anda.sh
    echo "  ✅ Backup completed"
else
    echo "  ⚠️  Backup script not found, skipping"
fi

# Stop main service (this will also trigger memory worker cleanup)
echo "  Stopping chatgpt-duck.service..."
sudo systemctl stop chatgpt-duck.service

# Stop memory worker
echo "  Stopping duck-memory-worker.service..."
sudo systemctl stop duck-memory-worker.service

# NOTE: duck-control.service stoppes IKKE her.
# Denne scripten kalles fra duck-control, så den må fortsette å kjøre
# til sudo shutdown -h now tar over.

# Stop fan control (if running)
if systemctl is-active --quiet fan-control.service; then
    echo "  Stopping fan-control.service..."
    sudo systemctl stop fan-control.service
fi

# Wait for services to shut down cleanly
sleep 3

# Clean up any temporary files
echo "  Cleaning up temporary files..."
rm -f /tmp/duck_*.txt 2>/dev/null

echo "✅ All Anda services stopped gracefully"
