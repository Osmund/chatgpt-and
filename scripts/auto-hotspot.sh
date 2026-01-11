#!/bin/bash
# Auto-hotspot script: Starter hotspot hvis ingen WiFi-tilkobling finnes
# SAFE VERSION: Korte timeouts og failsafe

# Vent litt for at NetworkManager skal starte ordentlig
sleep 5

echo "Sjekker WiFi-tilkobling..." | logger -t auto-hotspot

# Sjekk om vi har en aktiv WiFi-tilkobling (med timeout)
if timeout 5 nmcli -t -f ACTIVE,SSID dev wifi | grep "^yes:" > /dev/null 2>&1; then
    echo "WiFi allerede tilkoblet og aktivt, hopper over hotspot" | logger -t auto-hotspot
    exit 0
fi

echo "Ingen aktiv WiFi-forbindelse funnet" | logger -t auto-hotspot

# Prøv å koble til kjente nettverk først (vent 5 sekunder)
echo "Prøver å koble til kjente nettverk..." | logger -t auto-hotspot
sleep 5

# Sjekk igjen (med timeout)
if timeout 5 nmcli -t -f ACTIVE,SSID dev wifi | grep "^yes:" > /dev/null 2>&1; then
    echo "WiFi tilkoblet!" | logger -t auto-hotspot
    exit 0
fi

# Fortsatt ingen tilkobling, start hotspot
echo "Starter WiFi hotspot..." | logger -t auto-hotspot

# Sett LED til gul for AP-modus (kjør som admog for GPIO-tilgang)
timeout 5 sudo -u admog /home/admog/Code/chatgpt-and/.venv/bin/python3 -c "from rgb_duck import set_yellow; set_yellow()" 2>/dev/null &

# Bruk eksisterende Hotspot connection profile
timeout 10 nmcli connection up Hotspot

if [ $? -eq 0 ]; then
    echo "Hotspot startet vellykket" | logger -t auto-hotspot
    
    # Start WiFi-portal
    sleep 3
    /home/admog/Code/chatgpt-and/wifi-portal.py &
    echo "WiFi-portal startet" | logger -t auto-hotspot
else
    echo "Kunne ikke starte hotspot" | logger -t auto-hotspot
    exit 1
fi
