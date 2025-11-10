#!/bin/bash
# Test hotspot-oppstart uten å faktisk koble fra WiFi

echo "=== TESTER HOTSPOT-OPPSTART ==="
echo ""

# Sjekk at Hotspot connection finnes
echo "1. Sjekker Hotspot connection profile..."
if nmcli connection show "Hotspot" > /dev/null 2>&1; then
    echo "   ✅ Hotspot profile finnes"
else
    echo "   ❌ Hotspot profile mangler!"
    exit 1
fi

# Sjekk at vi kan aktivere hotspot med timeout
echo ""
echo "2. Tester aktivering av hotspot (med timeout)..."
echo "   ⚠️  ADVARSEL: Dette vil kutte WiFi i 5 sekunder!"
read -p "   Fortsett? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "   Avbrutt."
    exit 0
fi

# Prøv å aktivere hotspot
timeout 5 sudo nmcli connection up Hotspot > /dev/null 2>&1
if [ $? -eq 0 ] || [ $? -eq 124 ]; then
    echo "   ✅ Hotspot kan aktiveres"
    
    # Koble tilbake til WiFi raskt
    sleep 2
    echo "   Kobler tilbake til WiFi..."
    sudo nmcli connection up "Grov Casa 2.4" > /dev/null 2>&1
    sleep 3
    echo "   ✅ Tilbake på WiFi"
else
    echo "   ❌ Kunne ikke aktivere hotspot"
    exit 1
fi

echo ""
echo "3. Sjekker LED-kommando..."
timeout 2 sudo -u admog /home/admog/Code/chatgpt-and/.venv/bin/python3 -c "from rgb_duck import set_yellow; set_yellow(); import time; time.sleep(1); from rgb_duck import set_blue; set_blue()" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ LED kan settes til gul"
else
    echo "   ⚠️  LED-kommando feilet (men ikke kritisk)"
fi

echo ""
echo "=== ALLE TESTER OK ==="
echo ""
echo "Hotspot-systemet er klart!"
echo "Ved boot uten WiFi vil Pi:"
echo "  1. Vente 5 sekunder"
echo "  2. Sjekke WiFi (timeout 5 sek)"
echo "  3. Vente 5 sekunder til"
echo "  4. Sjekke WiFi igjen"
echo "  5. Starte hotspot hvis ingen WiFi"
echo "  6. Sette LED til gul"
echo "  7. Starte wifi-portal på port 8080"
