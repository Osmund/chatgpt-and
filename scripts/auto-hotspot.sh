#!/bin/bash
# Auto-hotspot script: Starter hotspot hvis ingen WiFi-tilkobling finnes
# IMPROVED VERSION: Better checks, cleanup, and monitoring

LOG_TAG="auto-hotspot"
HOTSPOT_NAME="Hotspot"
VENV_PYTHON="/home/admog/Code/chatgpt-and/.venv/bin/python3"
PORTAL_SCRIPT="/home/admog/Code/chatgpt-and/wifi-portal.py"
PORTAL_PID_FILE="/tmp/wifi-portal.pid"

log() {
    echo "$1" | logger -t "$LOG_TAG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Vent litt for at NetworkManager skal starte ordentlig
sleep 5

log "Sjekker WiFi-tilkobling..."

# Funksjon for å sjekke WiFi-tilkobling
check_wifi_connected() {
    # Sjekk om vi har internett-tilkobling (ping test)
    if timeout 3 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
        return 0  # Connected
    fi
    
    # Fallback: Sjekk om noen WiFi-connection er aktiv (IKKE vårt eget hotspot)
    local active=$(nmcli -t -f NAME,TYPE,STATE connection show --active | grep ":802-11-wireless:activated$" | grep -v "^Hotspot:")
    if [ -n "$active" ]; then
        return 0  # Connected
    fi
    
    return 1  # Not connected
}

# Funksjon for å sjekke om hotspot kjører
is_hotspot_running() {
    nmcli -t -f NAME,TYPE,STATE connection show --active | grep "^${HOTSPOT_NAME}:" | grep ":activated$" > /dev/null 2>&1
    return $?
}

# Funksjon for å stoppe hotspot
stop_hotspot() {
    log "Stopper hotspot..."
    
    # Lagre om monitor kaller oss (WiFi kom tilbake)
    local restart_duck="${1:-no}"
    
    # Prøv å stoppe hotspot
    if nmcli connection down "$HOTSPOT_NAME" 2>/dev/null; then
        log "Hotspot stoppet vellykket"
    else
        log "ADVARSEL: Kunne ikke stoppe hotspot (kan allerede være nede)"
    fi
    
    # Stopp wifi-portal hvis den kjører
    if [ -f "$PORTAL_PID_FILE" ]; then
        local pid=$(cat "$PORTAL_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid" 2>/dev/null
            log "WiFi-portal stoppet (PID: $pid)"
        fi
        rm -f "$PORTAL_PID_FILE"
    fi
    
    # Stopp monitor hvis den kjører
    if [ -f "/tmp/hotspot_monitor.pid" ]; then
        local monitor_pid=$(cat "/tmp/hotspot_monitor.pid")
        if ps -p "$monitor_pid" > /dev/null 2>&1; then
            kill "$monitor_pid" 2>/dev/null
            log "Monitor stoppet (PID: $monitor_pid)"
        fi
        rm -f "/tmp/hotspot_monitor.pid"
    fi
    
    # Slå av gul LED
    sudo -u admog "$VENV_PYTHON" -c "from rgb_duck import off; off()" 2>/dev/null
    
    # Restart Duck service hvis WiFi kom tilbake (restart håndterer både kjører/ikke kjører)
    if [ "$restart_duck" = "yes" ]; then
        log "Restarter Duck service..."
        sudo systemctl restart chatgpt-duck.service
    fi
}

# Sjekk om hotspot allerede kjører
if is_hotspot_running; then
    log "Hotspot kjører allerede - sjekker om WiFi er tilbake..."
    if check_wifi_connected; then
        log "WiFi er tilbake! Stopper hotspot..."
        stop_hotspot
        exit 0
    else
        log "WiFi fortsatt utilgjengelig, sjekker portal og monitor..."
        
        # Sjekk om portal kjører, start hvis mangler
        if [ -f "$PORTAL_PID_FILE" ]; then
            portal_pid=$(cat "$PORTAL_PID_FILE")
            if ! ps -p "$portal_pid" > /dev/null 2>&1; then
                log "Portal er død, starter på nytt..."
                "$VENV_PYTHON" "$PORTAL_SCRIPT" &
                PORTAL_PID=$!
                echo $PORTAL_PID > "$PORTAL_PID_FILE"
                log "WiFi-portal startet (PID: $PORTAL_PID)"
            else
                log "Portal kjører allerede (PID: $portal_pid)"
            fi
        else
            log "Portal ikke startet, starter nå..."
            "$VENV_PYTHON" "$PORTAL_SCRIPT" &
            PORTAL_PID=$!
            echo $PORTAL_PID > "$PORTAL_PID_FILE"
            log "WiFi-portal startet (PID: $PORTAL_PID)"
        fi
        
        # Sjekk om monitor kjører, start hvis mangler
        if [ -f "/tmp/hotspot_monitor.pid" ]; then
            monitor_pid=$(cat "/tmp/hotspot_monitor.pid")
            if ! ps -p "$monitor_pid" > /dev/null 2>&1; then
                log "Monitor er død, starter på nytt..."
                (
                    sleep 30
                    while true; do
                        sleep 60
                        if check_wifi_connected; then
                            log "WiFi-tilkobling gjenopprettet! Stopper hotspot..."
                            stop_hotspot "yes"
                            rm -f /tmp/hotspot_monitor.pid
                            break
                        fi
                    done
                ) &
                MONITOR_PID=$!
                echo $MONITOR_PID > /tmp/hotspot_monitor.pid
                log "Monitor startet (PID: $MONITOR_PID)"
            else
                log "Monitor kjører allerede (PID: $monitor_pid)"
            fi
        else
            log "Monitor ikke startet, starter nå..."
            (
                sleep 30
                while true; do
                    sleep 60
                    if check_wifi_connected; then
                        log "WiFi-tilkobling gjenopprettet! Stopper hotspot..."
                        stop_hotspot "yes"
                        rm -f /tmp/hotspot_monitor.pid
                        break
                    fi
                done
            ) &
            MONITOR_PID=$!
            echo $MONITOR_PID > /tmp/hotspot_monitor.pid
            log "Monitor startet (PID: $MONITOR_PID)"
        fi
        
        # Sørg for at LED er gul
        sudo -u admog "$VENV_PYTHON" -c "from rgb_duck import set_yellow; set_yellow()" 2>/dev/null
        
        exit 0
    fi
fi

# Sjekk om vi har WiFi-tilkobling
if check_wifi_connected; then
    log "WiFi allerede tilkoblet og aktivt, hopper over hotspot"
    exit 0
fi

log "Ingen aktiv WiFi-forbindelse funnet"

# Prøv å koble til kjente nettverk først
log "Prøver å koble til kjente nettverk..."
nmcli device wifi rescan 2>/dev/null
sleep 5

# Sjekk igjen
if check_wifi_connected; then
    log "WiFi tilkoblet etter rescan!"
    exit 0
fi

# Vent litt ekstra (WiFi kan ta tid etter boot)
log "Venter 10 sekunder til for WiFi..."
sleep 10

# Siste sjekk før hotspot
if check_wifi_connected; then
    log "WiFi tilkoblet etter ekstra ventetid!"
    exit 0
fi
    log "WiFi tilkoblet!"
    exit 0
fi

# Fortsatt ingen tilkobling, start hotspot
log "Starter WiFi hotspot..."

# Sett LED til gul blinking for AP-modus (kjør som admog for GPIO-tilgang)
sudo -u admog "$VENV_PYTHON" -c "from rgb_duck import blink_yellow; blink_yellow()" 2>/dev/null

# Voice announcement: Hotspot starter med IP-adresse
HOTSPOT_IP="192.168.50.1"
echo "Jeg kunne ikke koble til WiFi, så jeg starter hotspot nå. Koble til mitt nettverk ChatGPT-Duck med passord kvakk kvakk kvakk kvakk. Gå til ${HOTSPOT_IP} i nettleseren for å sette opp WiFi." > /tmp/duck_hotspot_announcement.txt

# Bruk eksisterende Hotspot connection profile
if timeout 10 nmcli connection up "$HOTSPOT_NAME" 2>&1 | logger -t "$LOG_TAG"; then
    log "Hotspot startet vellykket"
    
    # Sett LED til fast gul
    sudo -u admog "$VENV_PYTHON" -c "from rgb_duck import set_yellow; set_yellow()" 2>/dev/null
    
    # Start WiFi-portal med riktig Python og PID-tracking
    sleep 3
    
    # Stopp gammel portal hvis den kjører
    if [ -f "$PORTAL_PID_FILE" ]; then
        old_pid=$(cat "$PORTAL_PID_FILE")
        if ps -p "$old_pid" > /dev/null 2>&1; then
            kill "$old_pid" 2>/dev/null
        fi
    fi
    
    # Start ny portal
    "$VENV_PYTHON" "$PORTAL_SCRIPT" &
    PORTAL_PID=$!
    echo $PORTAL_PID > "$PORTAL_PID_FILE"
    log "WiFi-portal startet (PID: $PORTAL_PID)"
    
    # Start monitor i bakgrunn som sjekker om WiFi kommer tilbake
    # Lagre PID for å kunne stoppe monitoren senere
    (
        sleep 30  # Vent 30 sek før første sjekk
        while true; do
            sleep 60  # Sjekk hvert minutt
            if check_wifi_connected; then
                log "WiFi-tilkobling gjenopprettet! Stopper hotspot..."
                stop_hotspot "yes"
                # Slett monitor PID fil
                rm -f /tmp/hotspot_monitor.pid
                break
            fi
        done
    ) &
    MONITOR_PID=$!
    echo $MONITOR_PID > /tmp/hotspot_monitor.pid
    log "Monitor startet (PID: $MONITOR_PID)"
    
else
    log "FEIL: Kunne ikke starte hotspot"
    sudo -u admog "$VENV_PYTHON" -c "from rgb_duck import off; off()" 2>/dev/null
    exit 1
fi
