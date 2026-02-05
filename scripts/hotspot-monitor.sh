#!/bin/bash
# Hotspot monitor: Sjekker periodisk om WiFi-nettverk er tilgjengelig igjen
# Startes av auto-hotspot når hotspot aktiveres
# Stopper hotspot og kobler til WiFi når et kjent nettverk dukker opp

HOTSPOT_NAME="Hotspot"
VENV_PYTHON="/home/admog/Code/chatgpt-and/.venv/bin/python3"
CHECK_INTERVAL=60  # Sjekk hvert minutt
LOG_TAG="hotspot-monitor"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$1" | logger -t "$LOG_TAG"
}

log "Hotspot monitor startet"
log "Venter 60s før første sjekk..."
sleep 60

while true; do
    # Sjekk om hotspot fortsatt kjører
    if ! nmcli -t -f NAME,STATE connection show --active 2>/dev/null | grep -q "^${HOTSPOT_NAME}:activated"; then
        log "Hotspot er ikke aktiv lenger, avslutter monitor"
        exit 0
    fi
    
    # Scan etter tilgjengelige nettverk
    nmcli device wifi rescan 2>/dev/null
    sleep 3
    
    # Hent lagrede nettverk (autoconnect)
    local_ssids=$(nmcli -t -f NAME,TYPE,AUTOCONNECT connection show | grep ':802-11-wireless:yes' | cut -d: -f1)
    
    # Sjekk om noen av de lagrede nettverkene er synlige
    for ssid in $local_ssids; do
        if [ "$ssid" = "$HOTSPOT_NAME" ]; then
            continue  # Hopp over hotspot-profilen
        fi
        
        if nmcli -t -f SSID device wifi list 2>/dev/null | grep -q "^${ssid}$"; then
            log "Fant kjent nettverk: $ssid"
            log "Stopper hotspot og kobler til WiFi..."
            
            # Stopp portal og monitor-relaterte services
            systemctl stop wifi-portal.service 2>/dev/null
            
            # Stopp hotspot
            nmcli connection down "$HOTSPOT_NAME" 2>/dev/null
            sleep 2
            
            # Koble til det kjente nettverket
            if nmcli connection up "$ssid" 2>&1; then
                log "Koblet til $ssid!"
                
                # Slå av gul LED
                "$VENV_PYTHON" -c "from rgb_duck import off; off()" 2>/dev/null
                
                # Restart duck service
                log "Restarter chatgpt-duck service..."
                systemctl restart chatgpt-duck.service 2>/dev/null
                
                log "Monitor avslutter - WiFi gjenopprettet"
                exit 0
            else
                log "Kunne ikke koble til $ssid, prøver igjen senere..."
                # Start hotspot igjen
                nmcli connection up "$HOTSPOT_NAME" 2>/dev/null
                systemctl start wifi-portal.service 2>/dev/null
            fi
        fi
    done
    
    sleep "$CHECK_INTERVAL"
done
