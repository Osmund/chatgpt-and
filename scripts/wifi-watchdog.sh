#!/bin/bash
# NetworkManager dispatcher script
# Triggers hotspot when WiFi disconnects

INTERFACE=$1
ACTION=$2

LOG_TAG="wifi-watchdog"
AUTO_HOTSPOT="/home/admog/Code/chatgpt-and/scripts/auto-hotspot.sh"

log() {
    echo "$1" | logger -t "$LOG_TAG"
}

# Only trigger on WiFi interfaces going down
if [ "$INTERFACE" != "wlan0" ]; then
    exit 0
fi

case "$ACTION" in
    down)
        log "WiFi interface $INTERFACE went down - checking if hotspot is needed"
        
        # Wait a moment to see if WiFi reconnects
        sleep 5
        
        # Check if any WiFi is connected
        if ! nmcli -t -f NAME,TYPE,STATE connection show --active | grep ":802-11-wireless:activated$" | grep -v "^Hotspot:" > /dev/null 2>&1; then
            # Check if we have internet
            if ! timeout 3 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
                log "No WiFi connection available - triggering auto-hotspot"
                "$AUTO_HOTSPOT" &
            else
                log "Internet available via other means - skipping hotspot"
            fi
        else
            log "WiFi already reconnected - skipping hotspot"
        fi
        ;;
    
    connectivity-change)
        # Check if we lost connectivity
        CONNECTIVITY=$(nmcli -t -f CONNECTIVITY general)
        if [ "$CONNECTIVITY" = "none" ] || [ "$CONNECTIVITY" = "limited" ]; then
            log "Connectivity changed to $CONNECTIVITY - checking if hotspot is needed"
            
            sleep 5
            
            # Check if any WiFi is connected
            if ! nmcli -t -f NAME,TYPE,STATE connection show --active | grep ":802-11-wireless:activated$" | grep -v "^Hotspot:" > /dev/null 2>&1; then
                # Double-check internet
                if ! timeout 3 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
                    log "No connectivity and no WiFi - triggering auto-hotspot"
                    "$AUTO_HOTSPOT" &
                fi
            fi
        fi
        ;;
esac

exit 0
