#!/bin/bash
# Trygg installasjon av duck-tjenester
# Kjør dette manuelt når du er klar: ./install-services.sh

echo "=== Installerer Duck-tjenester ==="

# Kopier service-filer
echo "Kopierer service-filer..."
sudo cp /home/admog/Code/chatgpt-and/chatgpt-duck.service /etc/systemd/system/
sudo cp /home/admog/Code/chatgpt-and/auto-hotspot.service /etc/systemd/system/
sudo cp /home/admog/Code/chatgpt-and/duck-control.service /etc/systemd/system/
sudo cp /home/admog/Code/chatgpt-and/fan-control.service /etc/systemd/system/
sudo cp /home/admog/Code/chatgpt-and/duck-memory-worker.service /etc/systemd/system/
sudo cp /home/admog/Code/chatgpt-and/duck-memory-hygiene.service /etc/systemd/system/
sudo cp /home/admog/Code/chatgpt-and/duck-memory-hygiene.timer /etc/systemd/system/

# Reload systemd
echo "Reloader systemd..."
sudo systemctl daemon-reload

# Enable tjenester (men ikke start dem ennå)
echo "Enabler tjenester..."
sudo systemctl enable chatgpt-duck.service
sudo systemctl enable auto-hotspot.service
sudo systemctl enable duck-control.service
sudo systemctl enable fan-control.service
sudo systemctl enable duck-memory-worker.service
sudo systemctl enable duck-memory-hygiene.timer

echo ""
echo "=== Tjenester installert! ==="
echo ""
echo "For å starte manuelt:"
echo "  sudo systemctl start chatgpt-duck.service"
echo "  sudo systemctl start auto-hotspot.service"
echo "  sudo systemctl start duck-control.service"
echo "  sudo systemctl start fan-control.service"
echo "  sudo systemctl start duck-memory-worker.service"
echo ""
echo "For å teste auto-hotspot (simuler boot uten WiFi):"
echo "  sudo /home/admog/Code/chatgpt-and/auto-hotspot.sh"
echo ""
echo "For å se logger:"
echo "  sudo journalctl -u chatgpt-duck.service -f"
echo "  sudo journalctl -u auto-hotspot.service -f"
echo "  sudo journalctl -u fan-control.service -f"
echo "  sudo journalctl -u duck-memory-worker.service -f"
echo "  sudo journalctl -u duck-memory-hygiene.service -f"
echo ""
echo "For å teste hygiene manuelt:"
echo "  sudo systemctl start duck-memory-hygiene.service"
echo ""
echo "For å avinstallere:"
echo "  sudo systemctl disable chatgpt-duck.service auto-hotspot.service duck-control.service fan-control.service duck-memory-worker.service duck-memory-hygiene.timer"
echo "  sudo rm /etc/systemd/system/chatgpt-duck.service /etc/systemd/system/auto-hotspot.service /etc/systemd/system/fan-control.service /etc/systemd/system/duck-memory-worker.service /etc/systemd/system/duck-memory-hygiene.service /etc/systemd/system/duck-memory-hygiene.timer"
echo "  sudo systemctl daemon-reload"
