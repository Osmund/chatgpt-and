#!/usr/bin/env python3
"""
ChatGPT Duck - Fan Control Service
Overvåker CPU-temperatur og styrer 5V vifte på GPIO 13.

Automatisk modus:
- Starter vifta når CPU > 55°C
- Stopper vifta når CPU < 50°C (hysterese)

Manuell overstyring:
- /tmp/duck_fan.txt: 'auto', 'on', 'off'
- /tmp/duck_fan_status.txt: Skriver status og temp
"""

import RPi.GPIO as GPIO
import time
import os

# GPIO-pin for vifte (blå ledning)
FAN_PIN = 13

# Temperaturgrenser
TEMP_ON = 55.0   # Start vifte ved 55°C
TEMP_OFF = 50.0  # Stopp vifte ved 50°C (hysterese for å unngå flapping)

# IPC-filer
FAN_MODE_FILE = "/tmp/duck_fan.txt"
FAN_STATUS_FILE = "/tmp/duck_fan_status.txt"

def get_cpu_temp():
    """Les CPU-temperatur fra /sys"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read().strip()) / 1000.0
            return temp
    except Exception as e:
        print(f"Feil ved lesing av CPU-temp: {e}", flush=True)
        return 0.0

def get_fan_mode():
    """Les ønsket viftemodus fra fil"""
    try:
        if os.path.exists(FAN_MODE_FILE):
            with open(FAN_MODE_FILE, 'r') as f:
                mode = f.read().strip().lower()
                if mode in ['auto', 'on', 'off']:
                    return mode
    except Exception as e:
        print(f"Feil ved lesing av fan mode: {e}", flush=True)
    return 'auto'  # Default til automatisk

def write_fan_status(mode, running, temp):
    """Skriv viftestatus til fil for kontrollpanel"""
    try:
        status = {
            'mode': mode,
            'running': running,
            'temp': temp
        }
        with open(FAN_STATUS_FILE, 'w') as f:
            f.write(f"{mode}|{running}|{temp:.1f}")
    except Exception as e:
        print(f"Feil ved skriving av fan status: {e}", flush=True)

def main():
    print("🌀 ChatGPT Duck Fan Control starter...", flush=True)
    
    # Sett opp GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(FAN_PIN, GPIO.OUT)
    
    fan_running = False
    last_mode = None
    
    try:
        while True:
            temp = get_cpu_temp()
            mode = get_fan_mode()
            
            # Logg modeendringer
            if mode != last_mode:
                print(f"Viftemodus endret til: {mode}", flush=True)
                last_mode = mode
            
            # Bestem om vifta skal gå
            should_run = fan_running  # Behold forrige tilstand som default
            
            if mode == 'on':
                should_run = True
            elif mode == 'off':
                should_run = False
            elif mode == 'auto':
                # Automatisk temperaturkontroll med hysterese
                if temp >= TEMP_ON:
                    should_run = True
                elif temp <= TEMP_OFF:
                    should_run = False
                # Hvis temp er mellom TEMP_OFF og TEMP_ON, behold forrige tilstand
            
            # Oppdater GPIO hvis tilstand endres
            if should_run != fan_running:
                if should_run:
                    GPIO.output(FAN_PIN, GPIO.HIGH)
                    print(f"✅ Vifte PÅ (temp: {temp:.1f}°C, mode: {mode})", flush=True)
                else:
                    GPIO.output(FAN_PIN, GPIO.LOW)
                    print(f"⏸️  Vifte AV (temp: {temp:.1f}°C, mode: {mode})", flush=True)
                fan_running = should_run
            
            # Skriv status
            write_fan_status(mode, fan_running, temp)
            
            # Vent 5 sekunder før neste sjekk
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n🛑 Fan control stopper...", flush=True)
    finally:
        GPIO.output(FAN_PIN, GPIO.LOW)
        GPIO.cleanup()
        print("GPIO cleanup ferdig", flush=True)

if __name__ == '__main__':
    # Sett default mode til auto ved oppstart
    if not os.path.exists(FAN_MODE_FILE):
        with open(FAN_MODE_FILE, 'w') as f:
            f.write('auto')
        os.chmod(FAN_MODE_FILE, 0o666)  # Gjør filen skrivbar for alle
    
    # Sørg for at statusfilen også er skrivbar
    if not os.path.exists(FAN_STATUS_FILE):
        with open(FAN_STATUS_FILE, 'w') as f:
            f.write('auto|False|0.0')
        os.chmod(FAN_STATUS_FILE, 0o666)
    
    main()
