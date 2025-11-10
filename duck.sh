#!/bin/bash

# Script for å kontrollere ChatGPT Duck servicen

case "$1" in
    start)
        echo "Starter ChatGPT Duck..."
        sudo systemctl start chatgpt-duck.service
        sleep 2
        sudo systemctl status chatgpt-duck.service --no-pager | head -10
        ;;
    stop)
        echo "Stopper ChatGPT Duck..."
        sudo systemctl stop chatgpt-duck.service
        echo "Stoppet."
        ;;
    restart)
        echo "Restarter ChatGPT Duck..."
        sudo systemctl restart chatgpt-duck.service
        sleep 2
        sudo systemctl status chatgpt-duck.service --no-pager | head -10
        ;;
    status)
        sudo systemctl status chatgpt-duck.service
        ;;
    logs)
        sudo journalctl -u chatgpt-duck.service -f
        ;;
    enable)
        echo "Aktiverer autostart..."
        sudo systemctl enable chatgpt-duck.service
        ;;
    disable)
        echo "Deaktiverer autostart..."
        sudo systemctl disable chatgpt-duck.service
        ;;
    control-start)
        echo "Starter kontrollpanel..."
        sudo systemctl start duck-control.service
        echo "Kontrollpanel: http://oduckberry:3000"
        ;;
    control-stop)
        echo "Stopper kontrollpanel..."
        sudo systemctl stop duck-control.service
        ;;
    control-status)
        sudo systemctl status duck-control.service
        ;;
    *)
        echo "Bruk: $0 {start|stop|restart|status|logs|enable|disable|control-start|control-stop|control-status}"
        exit 1
        ;;
esac
