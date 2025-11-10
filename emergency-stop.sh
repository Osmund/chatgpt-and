#!/bin/bash
# NØDSTOPP: Kjør dette hvis boot henger
# Kan kjøres fra recovery/safe mode

echo "=== NØDSTOPP AV DUCK-TJENESTER ==="

# Stopp alle tjenester
systemctl stop chatgpt-duck.service 2>/dev/null
systemctl stop auto-hotspot.service 2>/dev/null
systemctl stop duck-control.service 2>/dev/null

# Disable alle tjenester
systemctl disable chatgpt-duck.service 2>/dev/null
systemctl disable auto-hotspot.service 2>/dev/null
systemctl disable duck-control.service 2>/dev/null

# Maskér tjenestene for å forhindre start
ln -sf /dev/null /etc/systemd/system/auto-hotspot.service
ln -sf /dev/null /etc/systemd/system/chatgpt-duck.service

# Reload
systemctl daemon-reload

echo "=== ALLE DUCK-TJENESTER STOPPET OG DISABLED ==="
echo "Systemet er nå trygt. Kjør 'reboot' for å starte på nytt."
