#!/bin/bash
# Setup script for MAX98357A I2S Audio Amplifier

echo "=== MAX98357A Setup ==="
echo ""
echo "Tilkobling (koble til NÅ hvis ikke allerede gjort):"
echo "─────────────────────────────────────────────────────"
echo "MAX98357A      Raspberry Pi 5"
echo "─────────────────────────────────────────────────────"
echo "VIN       →    5V (pin 2 eller 4)"
echo "GND       →    Ground (pin 6)"
echo "SD        →    Ground (pin 6) - Normal drift"
echo "GAIN      →    Ground (pin 6) - 9dB forsterkning"
echo "DIN       →    GPIO 21 (pin 40)"
echo "BCLK      →    GPIO 18 (pin 12)"
echo "LRC       →    GPIO 19 (pin 35)"
echo "─────────────────────────────────────────────────────"
echo ""
echo "I2S er aktivert i /boot/firmware/config.txt"
echo ""
echo "Du må reboote for at endringene skal tre i kraft."
echo ""
read -p "Vil du reboote nå? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    sudo reboot
else
    echo ""
    echo "Husk å reboote senere med: sudo reboot"
    echo ""
    echo "Etter reboot, test med:"
    echo "  speaker-test -t wav -c 2"
    echo "eller"
    echo "  aplay /usr/share/sounds/alsa/Front_Center.wav"
fi
