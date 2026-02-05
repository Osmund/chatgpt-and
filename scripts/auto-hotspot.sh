#!/bin/bash
# Auto-hotspot: Starter hotspot + wifi-portal hvis ingen WiFi-tilkobling finnes
# Kjøres ved boot av auto-hotspot.service

HOTSPOT_NAME="Hotspot"
HOTSPOT_IP="192.168.50.1"
VENV_PYTHON="/home/admog/Code/chatgpt-and/.venv/bin/python3"
HOTSPOT_AUDIO="/home/admog/Code/chatgpt-and/audio/hotspot_announcement.wav"
LOG_TAG="auto-hotspot"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$1" | logger -t "$LOG_TAG"
}

# Sjekk om WiFi er tilkoblet (bare WiFi-link, ikke internett)
check_wifi() {
    local state=$(nmcli -t -f DEVICE,STATE device | grep "^wlan0:" | cut -d: -f2)
    if [ "$state" = "connected" ]; then
        local ip=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
        if [ -n "$ip" ]; then
            log "WiFi tilkoblet: $ip"
            return 0
        fi
    fi
    return 1
}

# ===== MAIN =====

log "=========================================="
log "Auto-hotspot starter"
log "=========================================="

# Vent på at NetworkManager prøver autoconnect
log "Venter 15s på NetworkManager..."
sleep 15

# Sjekk WiFi
if check_wifi; then
    log "WiFi OK - ingen hotspot nødvendig"
    exit 0
fi

# Prøv rescan + vent
log "Ingen WiFi, prøver rescan..."
nmcli device wifi rescan 2>/dev/null
sleep 10

if check_wifi; then
    log "WiFi OK etter rescan"
    exit 0
fi

# === Ingen WiFi - start hotspot ===
log "Starter hotspot..."

# Sett gul LED
"$VENV_PYTHON" -c "from rgb_duck import blink_yellow; blink_yellow()" 2>/dev/null

# Start hotspot
if ! timeout 10 nmcli connection up "$HOTSPOT_NAME" 2>&1; then
    log "FEIL: Kunne ikke starte hotspot"
    "$VENV_PYTHON" -c "from rgb_duck import off; off()" 2>/dev/null
    exit 1
fi

log "Hotspot startet på $HOTSPOT_IP"
"$VENV_PYTHON" -c "from rgb_duck import set_yellow; set_yellow()" 2>/dev/null

# Spill av announcement WAV (i bakgrunnen så det ikke blokkerer)
if [ -f "$HOTSPOT_AUDIO" ]; then
    log "Spiller hotspot announcement..."
    sudo -u admog aplay -q "$HOTSPOT_AUDIO" 2>/dev/null &
fi

# Start wifi-portal service (egen service med Restart=always)
log "Starter wifi-portal service..."
systemctl start wifi-portal.service

# Start hotspot-monitor service (sjekker om WiFi kommer tilbake)
log "Starter hotspot-monitor service..."
systemctl start hotspot-monitor.service

log "Alt startet. Portal: http://$HOTSPOT_IP"
