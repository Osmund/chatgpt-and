#!/bin/bash
# Setup script for WiFi hotspot
# Opprett en permanent hotspot-connection som auto-hotspot.sh kan bruke

HOTSPOT_NAME="Hotspot"
HOTSPOT_SSID="ChatGPT-Duck"
HOTSPOT_PASSWORD="kvakkkvakk"
HOTSPOT_IP="192.168.50.1"

echo "Oppretter WiFi hotspot-konfigurasjon..."
echo "  SSID: $HOTSPOT_SSID"
echo "  Passord: $HOTSPOT_PASSWORD"
echo "  IP: $HOTSPOT_IP"

# Sjekk om hotspot allerede eksisterer
if nmcli connection show "$HOTSPOT_NAME" &>/dev/null; then
    echo "⚠️  Hotspot '$HOTSPOT_NAME' eksisterer allerede"
    read -p "Vil du slette og gjenopprette? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo nmcli connection delete "$HOTSPOT_NAME"
        echo "✓ Slettet gammel hotspot"
    else
        echo "Avbryter..."
        exit 0
    fi
fi

# Opprett hotspot connection
sudo nmcli connection add \
    type wifi \
    con-name "$HOTSPOT_NAME" \
    ifname wlan0 \
    ssid "$HOTSPOT_SSID" \
    mode ap \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASSWORD" \
    ipv4.method shared \
    ipv4.address "$HOTSPOT_IP/24" \
    connection.autoconnect no \
    connection.autoconnect-priority -10

if [ $? -eq 0 ]; then
    echo "✅ Hotspot opprettet!"
    echo ""
    echo "Detaljer:"
    echo "  - Connection navn: $HOTSPOT_NAME"
    echo "  - SSID (nettverksnavn): $HOTSPOT_SSID"
    echo "  - Passord: $HOTSPOT_PASSWORD"
    echo "  - IP-adresse: $HOTSPOT_IP"
    echo "  - Portal: http://$HOTSPOT_IP"
    echo ""
    echo "Hotspot vil automatisk starte når WiFi ikke er tilgjengelig."
    echo "For å teste: sudo nmcli connection up $HOTSPOT_NAME"
else
    echo "❌ Feil ved opprettelse av hotspot"
    exit 1
fi
