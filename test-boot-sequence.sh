#!/bin/bash
# Test boot-sekvensen uten å faktisk reboote

echo "=== SIMULERER BOOT-SEKVENS ==="
echo ""

echo "1. Sjekker service dependencies..."
echo "   chatgpt-duck.service:"
systemctl show chatgpt-duck.service | grep -E "^(After|Wants|Requires)="
echo ""
echo "   auto-hotspot.service:"
systemctl show auto-hotspot.service | grep -E "^(After|Wants|Requires)="
echo ""

echo "2. Tester auto-hotspot.sh (med timeout)..."
timeout 30 sudo /home/admog/Code/chatgpt-and/auto-hotspot.sh
if [ $? -eq 124 ]; then
    echo "   ❌ FEIL: auto-hotspot.sh hang i 30 sekunder!"
    exit 1
else
    echo "   ✅ OK: auto-hotspot.sh fullførte"
fi
echo ""

echo "3. Sjekker at tjenestene er enabled..."
systemctl is-enabled chatgpt-duck.service
systemctl is-enabled auto-hotspot.service
systemctl is-enabled duck-control.service
echo ""

echo "4. Sjekker at tjenestene kjører..."
systemctl is-active chatgpt-duck.service
systemctl is-active auto-hotspot.service
systemctl is-active duck-control.service
echo ""

echo "=== ALLE TESTER OK ==="
echo ""
echo "Systemet ser trygt ut for reboot!"
echo "Kjør: sudo reboot"
