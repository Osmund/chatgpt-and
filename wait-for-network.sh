#!/bin/bash
# Vent på at vi har en aktiv nettverkstilkobling (ikke AP)
# SAFE VERSION: Gir opp raskt og lar servicen starte uansett

echo "Sjekker nettverkstilkobling..." | logger -t wait-for-network

# Sjekk bare 3 ganger (15 sekunder totalt), så gir vi opp
for i in {1..3}; do
    # Sjekk om vi har en aktiv WiFi-forbindelse
    if nmcli -t -f ACTIVE,TYPE dev | grep "^yes:wifi" > /dev/null 2>&1; then
        echo "Nettverkstilkobling OK!" | logger -t wait-for-network
        exit 0
    fi
    
    sleep 5
done

echo "Starter uten nettverkstilkobling" | logger -t wait-for-network
exit 0  # ALLTID exit 0 for å unngå å blokkere boot
