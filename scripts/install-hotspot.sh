#!/bin/bash
# ============================================================
# Installasjon av Auto-Hotspot + WiFi Portal for ChatGPT Duck
# ============================================================
# Kjør dette scriptet på den nye ducken (f.eks. Seven)
# Forutsetninger:
#   - Git-repoet er klonet til /home/admog/Code/chatgpt-and
#   - Python venv finnes i .venv/
#   - NetworkManager er installert
#   - Hotspot connection "Hotspot" er konfigurert i NetworkManager
#
# Bruk:  sudo bash install-hotspot.sh
# ============================================================

set -e

DUCK_DIR="/home/admog/Code/chatgpt-and"
SERVICE_DIR="/etc/systemd/system"

# Farger
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

echo ""
echo "============================================"
echo "  ChatGPT Duck - Auto-Hotspot Installasjon"
echo "============================================"
echo ""

# Sjekk at vi kjører som root
if [ "$EUID" -ne 0 ]; then
    err "Kjør med sudo: sudo bash install-hotspot.sh"
    exit 1
fi

# Sjekk at duck-mappen finnes
if [ ! -d "$DUCK_DIR" ]; then
    err "Duck-mappen ikke funnet: $DUCK_DIR"
    exit 1
fi

# Sjekk at venv finnes
if [ ! -f "$DUCK_DIR/.venv/bin/python3" ]; then
    err "Python venv ikke funnet: $DUCK_DIR/.venv/bin/python3"
    exit 1
fi

# ---- 1. Sjekk/opprett Hotspot connection ----
echo ""
echo "--- 1. Sjekker Hotspot connection ---"
if nmcli connection show "Hotspot" &>/dev/null; then
    log "Hotspot connection finnes allerede"
else
    warn "Hotspot connection mangler - oppretter..."
    nmcli connection add \
        type wifi \
        con-name "Hotspot" \
        autoconnect no \
        wifi.mode ap \
        wifi.ssid "ChatGPT-Duck" \
        wifi.band bg \
        wifi.channel 6 \
        ipv4.method shared \
        ipv4.addresses "192.168.50.1/24" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "kvakkkvakk"
    log "Hotspot connection opprettet (SSID: ChatGPT-Duck, passord: kvakkkvakk)"
fi

# ---- 2. Gjør scripts kjørbare ----
echo ""
echo "--- 2. Setter filrettigheter ---"
chmod +x "$DUCK_DIR/scripts/auto-hotspot.sh"
chmod +x "$DUCK_DIR/scripts/hotspot-monitor.sh"
log "Scripts er kjørbare"

# ---- 3. Installer systemd services ----
echo ""
echo "--- 3. Installerer systemd services ---"

# Stopp eksisterende services først
systemctl stop auto-hotspot.service 2>/dev/null || true
systemctl stop wifi-portal.service 2>/dev/null || true
systemctl stop hotspot-monitor.service 2>/dev/null || true

# Kopier service-filer
cp "$DUCK_DIR/services/auto-hotspot.service" "$SERVICE_DIR/"
cp "$DUCK_DIR/services/wifi-portal.service" "$SERVICE_DIR/"
cp "$DUCK_DIR/services/hotspot-monitor.service" "$SERVICE_DIR/"
log "Service-filer kopiert til $SERVICE_DIR"

# Reload systemd
systemctl daemon-reload
log "systemd reloaded"

# Enable auto-hotspot (kjører ved boot)
systemctl enable auto-hotspot.service
log "auto-hotspot.service enabled (kjører ved boot)"

# wifi-portal og hotspot-monitor skal IKKE enables - de startes on-demand
log "wifi-portal.service og hotspot-monitor.service er on-demand (startes av auto-hotspot)"

# ---- 4. Sjekk audio-fil ----
echo ""
echo "--- 4. Sjekker hotspot announcement ---"
if [ -f "$DUCK_DIR/audio/hotspot_announcement.wav" ]; then
    log "hotspot_announcement.wav finnes ($(du -h "$DUCK_DIR/audio/hotspot_announcement.wav" | cut -f1))"
else
    warn "hotspot_announcement.wav mangler!"
    warn "Generer den med Azure TTS eller legg inn manuelt i $DUCK_DIR/audio/"
fi

# ---- 5. Installer duck-control WiFi-endringer ----
echo ""
echo "--- 5. Sjekker duck-control.service ---"
if systemctl is-enabled duck-control.service &>/dev/null; then
    log "duck-control.service er allerede enabled"
    systemctl restart duck-control.service
    log "duck-control.service restartet"
else
    if [ -f "$DUCK_DIR/services/duck-control.service" ]; then
        cp "$DUCK_DIR/services/duck-control.service" "$SERVICE_DIR/"
        systemctl daemon-reload
        systemctl enable duck-control.service
        systemctl start duck-control.service
        log "duck-control.service installert og startet"
    else
        warn "duck-control.service ikke funnet - kontrollpanel må settes opp manuelt"
    fi
fi

# ---- Oppsummering ----
echo ""
echo "============================================"
echo "  Installasjon fullført!"
echo "============================================"
echo ""
echo "Installerte services:"
echo "  auto-hotspot.service   - Kjører ved boot, sjekker WiFi"
echo "  wifi-portal.service    - WiFi-portal på http://192.168.50.1"
echo "  hotspot-monitor.service - Sjekker om WiFi kommer tilbake"
echo ""
echo "Flyt:"
echo "  1. Boot → auto-hotspot sjekker WiFi (25s)"
echo "  2. Ingen WiFi → hotspot starter (SSID: ChatGPT-Duck)"
echo "  3. WAV-fil spilles av"
echo "  4. WiFi-portal tilgjengelig på http://192.168.50.1"
echo "  5. Bruker velger nettverk + skriver passord"
echo "  6. Anda kobler til WiFi, hotspot stopper"
echo ""
echo "Hotspot-info:"
echo "  SSID:     ChatGPT-Duck"
echo "  Passord:  kvakkkvakk"
echo "  Portal:   http://192.168.50.1"
echo ""
echo "Test: sudo systemctl start auto-hotspot.service"
echo "Logg: journalctl -u auto-hotspot -u wifi-portal -u hotspot-monitor -f"
echo ""
