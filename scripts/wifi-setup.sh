#!/bin/bash

# Script for å sette opp WiFi hotspot for enkel nettverkskonfigurasjon

echo "=== WiFi Setup for ChatGPT Duck ==="
echo ""
echo "Dette scriptet hjelper deg med å:"
echo "1. Sette opp en WiFi hotspot når ingen nettverk er tilgjengelig"
echo "2. Koble til nye WiFi-nettverk via mobil"
echo ""

case "$1" in
    hotspot-on)
        echo "Starter WiFi hotspot..."
        sudo nmcli device wifi hotspot ssid "ChatGPT-Duck" password "kvakkkvakk"
        echo ""
        echo "✓ Hotspot startet!"
        echo "  SSID: ChatGPT-Duck"
        echo "  Passord: kvakkkvakk"
        echo "  IP: 10.42.0.1"
        echo ""
        echo "Koble til med mobilen og gå til http://10.42.0.1:8080"
        ;;
        
    hotspot-off)
        echo "Stopper WiFi hotspot..."
        sudo nmcli connection down Hotspot 2>/dev/null
        # Stopp også web-portalen hvis den kjører
        pkill 	-f wifi-portal.py 2>/dev/null
        echo "✓ Hotspot stoppet"
        ;;
    
    portal-start)
        echo "Starter WiFi setup portal..."
        # Stopp gammel prosess først
        pkill -f wifi-portal.py 2>/dev/null
        sleep 1
        /home/admog/Code/chatgpt-and/wifi-portal.py &
        sleep 2
        if pgrep -f wifi-portal.py > /dev/null; then
            echo "✓ Portal kjører på http://10.42.0.1:8080"
        else
            echo "✗ Kunne ikke starte portal"
        fi
        ;;
    
    portal-stop)
        echo "Stopper WiFi portal..."
        pkill -f wifi-portal.py
        echo "✓ Portal stoppet"
        ;;
        
    list)
        echo "Tilgjengelige WiFi-nettverk:"
        nmcli device wifi list
        ;;
        
    connect)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Bruk: $0 connect <SSID> <passord>"
            exit 1
        fi
        echo "Kobler til $2..."
        sudo nmcli device wifi connect "$2" password "$3"
        ;;
        
    status)
        echo "=== Nettverksstatus ==="
        nmcli connection show --active
        echo ""
        echo "=== IP-adresser ==="
        ip addr show wlan0 | grep inet
        ;;
        
    auto-hotspot)
        # Installer auto-hotspot script som starter hotspot ved boot
        echo "Aktiverer auto-hotspot ved oppstart..."
        
        if systemctl is-enabled auto-hotspot.service &>/dev/null; then
            echo "Auto-hotspot er allerede aktivert!"
        else
            sudo systemctl enable auto-hotspot.service
            echo "✓ Auto-hotspot aktivert!"
        fi
        
        echo ""
        echo "Pi'en vil nå automatisk:"
        echo "  1. Prøve å koble til kjente WiFi-nettverk ved oppstart"
        echo "  2. Hvis ingen nettverk finnes: Start hotspot 'ChatGPT-Duck'"
        echo "  3. Start WiFi-portal på http://10.42.0.1:8080"
        ;;
    
    auto-hotspot-disable)
        echo "Deaktiverer auto-hotspot..."
        sudo systemctl disable auto-hotspot.service
        echo "✓ Auto-hotspot deaktivert"
        ;;
    
    auto-hotspot-status)
        echo "=== Auto-hotspot status ==="
        systemctl status auto-hotspot.service --no-pager
        echo ""
        echo "=== Siste logger ==="
        journalctl -u auto-hotspot.service -n 20 --no-pager
        ;;
        
    *)
        echo "Bruk:"
        echo "  $0 hotspot-on              - Start WiFi hotspot manuelt"
        echo "  $0 hotspot-off             - Stopp WiFi hotspot"
        echo "  $0 portal-start            - Start web-portal"
        echo "  $0 portal-stop             - Stopp web-portal"
        echo "  $0 list                    - Vis tilgjengelige WiFi-nettverk"
        echo "  $0 connect <SSID> <pw>     - Koble til WiFi-nettverk"
        echo "  $0 status                  - Vis nettverksstatus"
        echo "  $0 auto-hotspot            - Aktiver auto-hotspot ved boot"
        echo "  $0 auto-hotspot-disable    - Deaktiver auto-hotspot"
        echo "  $0 auto-hotspot-status     - Vis auto-hotspot status"
        exit 1
        ;;
esac
