#!/bin/bash
# Auto-hotspot script: Starter hotspot hvis ingen WiFi-tilkobling finnes
# IMPROVED VERSION: Better checks, cleanup, and monitoring

LOG_TAG="auto-hotspot"
HOTSPOT_NAME="Hotspot"
VENV_PYTHON="/home/admog/Code/chatgpt-and/.venv/bin/python3"
PORTAL_SCRIPT="/home/admog/Code/chatgpt-and/wifi-portal.py"
PORTAL_PID_FILE="/tmp/wifi-portal.pid"
LOG_DIR="/home/admog/Code/chatgpt-and/logs"
LOG_FILE="$LOG_DIR/auto-hotspot-$(date +%Y%m%d-%H%M%S).log"

# Opprett logg-mappe hvis den ikke finnes
mkdir -p "$LOG_DIR" 2>/dev/null || true

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$1" | logger -t "$LOG_TAG"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

# Start med å logge oppstart
log "=========================================="
log "Auto-hotspot starter (boot-tid: $(uptime -s))"
log "Nåværende tid: $(date)"
log "=========================================="

# Sjekk NetworkManager status
log "NetworkManager status: $(systemctl is-active NetworkManager)"

# List alle WiFi-connections
log "Lagrede WiFi-nettverk med autoconnect:"
nmcli -f NAME,TYPE,AUTOCONNECT connection show | grep wifi >> "$LOG_FILE"

# Vent litt for at NetworkManager skal starte ordentlig og prøve å koble til
# Vi må vente nok til at NetworkManager har prøvd alle autoconnect-nettverk
log "Venter 15 sekunder på at NetworkManager prøver å koble til..."
sleep 15

log "Sjekker WiFi-tilkobling nå..."
log "Aktive connections før test:"
nmcli -t -f NAME,TYPE,STATE connection show --active >> "$LOG_FILE"

# Funksjon for å sjekke WiFi-tilkobling
check_wifi_connected() {
    log "--- Starter internett-test ---"
    
    # Først: Sjekk om vi faktisk har en fullstendig aktiv WiFi-forbindelse
    local wifi_state=$(nmcli -t -f DEVICE,STATE device | grep "^wlan0:" | cut -d: -f2)
    log "WiFi device state: $wifi_state"
    
    if [ "$wifi_state" != "connected" ]; then
        log "✗ WiFi device ikke i 'connected' state - ingen tilkobling"
        return 1
    fi
    
    # Sjekk at vi faktisk har fått en IP-adresse
    local ip_addr=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
    if [ -z "$ip_addr" ]; then
        log "✗ Ingen IP-adresse på wlan0 - ingen tilkobling"
        return 1
    fi
    log "✓ WiFi tilkoblet med IP: $ip_addr"
    
    # Test 1: Ping til Google DNS
    log "Test 1: Pinger 8.8.8.8 (2 pakker, 5s timeout)..."
    if ! timeout 5 ping -c 2 8.8.8.8 > /dev/null 2>&1; then
        log "✗ Ping til 8.8.8.8 feilet - ingen IP-tilgang"
        return 1
    fi
    log "✓ Ping til 8.8.8.8 OK"
    
    # Test 2: Ping til Cloudflare DNS (ekstra test)
    log "Test 2: Pinger 1.1.1.1 (1 pakke, 5s timeout)..."
    if ! timeout 5 ping -c 1 1.1.1.1 > /dev/null 2>&1; then
        log "✗ Ping til 1.1.1.1 feilet"
        return 1
    fi
    log "✓ Ping til 1.1.1.1 OK"
    
    # Test 3: DNS-oppslag og HTTP-test (krever faktisk internett)
    log "Test 3: Pinger www.google.com (krever DNS, 5s timeout)..."
    if timeout 5 ping -c 1 www.google.com > /dev/null 2>&1; then
        log "✓ DNS-oppslag og ping til google.com OK - HAR INTERNETT!"
        return 0  # Connected with internet
    else
        log "✗ DNS-oppslag eller ping til google.com feilet - INGEN INTERNETT"
        return 1
    fi
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
                sudo "$VENV_PYTHON" "$PORTAL_SCRIPT" >> "$LOG_FILE" 2>&1 &
                PORTAL_PID=$!
                echo $PORTAL_PID > "$PORTAL_PID_FILE"
                log "WiFi-portal startet (PID: $PORTAL_PID)"
            else
                log "Portal kjører allerede (PID: $portal_pid)"
            fi
        else
            log "Portal ikke startet, starter nå..."
            sudo "$VENV_PYTHON" "$PORTAL_SCRIPT" >> "$LOG_FILE" 2>&1 &
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

# Fortsatt ingen tilkobling, start hotspot
log "Starter WiFi hotspot..."

# Spill av offline hotspot announcement FØRST (pre-generert med Azure TTS)
HOTSPOT_AUDIO="/home/admog/Code/chatgpt-and/audio/hotspot_announcement.wav"
if [ -f "$HOTSPOT_AUDIO" ]; then
    log "Spiller offline hotspot announcement..."
    sudo -u admog aplay -q "$HOTSPOT_AUDIO" 2>/dev/null
    log "Hotspot announcement ferdig"
else
    log "⚠️ Offline hotspot announcement ikke funnet: $HOTSPOT_AUDIO"
fi

# Sett LED til gul blinking for AP-modus (kjør som admog for GPIO-tilgang)
sudo -u admog "$VENV_PYTHON" -c "from rgb_duck import blink_yellow; blink_yellow()" 2>/dev/null

# Voice announcement: Hotspot starter med IP-adresse (legacy, for TTS fallback)
HOTSPOT_IP="192.168.50.1"
echo "Jeg kunne ikke koble til WiFi, så jeg starter hotspot nå. Koble til mitt nettverk ChatGPT-Duck med passord kvakkkvakk. Gå til ${HOTSPOT_IP} i nettleseren for å sette opp WiFi." > /tmp/duck_hotspot_announcement.txt
# Gi admog-brukeren rettigheter til å lese filen
chmod 644 /tmp/duck_hotspot_announcement.txt
chown admog:admog /tmp/duck_hotspot_announcement.txt

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
    
    # Start ny portal (med sudo for å sikre port 80 tilgang)
    sudo "$VENV_PYTHON" "$PORTAL_SCRIPT" >> "$LOG_FILE" 2>&1 &
    PORTAL_PID=$!
    echo $PORTAL_PID > "$PORTAL_PID_FILE"
    log "WiFi-portal startet (PID: $PORTAL_PID)"
    
    # Verifiser at portalen faktisk startet (vent litt og sjekk prosess)
    sleep 2
    if ps -p $PORTAL_PID > /dev/null 2>&1; then
        log "✓ Portal prosess kjører"
        
        # Sjekk om port 80 eller 8080 lytter
        if timeout 5 bash -c "while ! netstat -tln 2>/dev/null | grep -q ':80\|:8080'; do sleep 0.5; done"; then
            PORTAL_PORT=$(netstat -tln 2>/dev/null | grep -E ':(80|8080) ' | head -1 | grep -oE ':[0-9]+' | tr -d ':')
            log "✓ Portal lytter på port $PORTAL_PORT"
            if [ "$PORTAL_PORT" != "80" ]; then
                log "⚠️  Portal bruker port $PORTAL_PORT i stedet for 80"
            fi
        else
            log "⚠️  Portal prosess kjører men lytter ikke på port 80/8080 ennå"
        fi
    else
        log "✗ FEIL: Portal prosess crashet ved oppstart! Sjekk logs."
    fi
    
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
