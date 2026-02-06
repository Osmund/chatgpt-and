#!/bin/bash
# Dreper VS Code Server når ingen SSH-tilkoblinger er aktive
# Kjøres av cron hvert 10. minutt

# Sjekk om det finnes aktive SSH-sesjoner
# VS Code Remote SSH bruker @notty (ikke pts/), så vi sjekker sshd-session prosesser
ACTIVE_SSH=$(pgrep -c 'sshd-session' 2>/dev/null || echo 0)

if [ "$ACTIVE_SSH" -eq 0 ]; then
    # Sjekk om vscode-server kjører
    if pgrep -f "vscode-server" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ingen SSH-sesjoner, dreper VS Code Server..." | logger -t cleanup-vscode
        pkill -f "vscode-server"
        sleep 2
        # Drep eventuelle gjenværende node-prosesser fra vscode
        pkill -f ".vscode-server/cli/servers"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] VS Code Server stoppet" | logger -t cleanup-vscode
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $ACTIVE_SSH SSH-sesjon(er) aktive, beholder VS Code Server" | logger -t cleanup-vscode
fi
