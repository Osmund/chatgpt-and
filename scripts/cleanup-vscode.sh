#!/bin/bash
# Dreper VS Code Server når ingen SSH-tilkoblinger er aktive
# Kjøres av cron hvert 10. minutt

# Sjekk om det finnes aktive SSH-sesjoner (utenom sshd-prosessen selv)
ACTIVE_SSH=$(who | grep -c 'pts/')

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
fi
