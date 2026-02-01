#!/usr/bin/env python3
"""
duck_beak.py
----------------
Servo control for the duck beak using a PCA9685 (I2C) + Adafruit ServoKit.

Hardware notes:
- PCA9685 I2C: SDA = GPIO2, SCL = GPIO3 (standard Raspberry Pi I2C pins)
- Servo signal connected to one PCA9685 channel (default SERVO_CHANNEL = 0)
- Use a separate 5V servo power supply (do NOT power heavy servos from the Pi 5V rail)

Software notes:
- This module uses `adafruit_servokit.ServoKit(channels=16)` to control the PCA9685.
- Calibrate your `CLOSE_US_DEFAULT` and `OPEN_US_DEFAULT` pulse widths and
    `CLOSE_DEG` / `OPEN_DEG` degrees for your particular servo to avoid mechanical
    stress or hitting the beak housing.

Updated: 2025-11-11 - migrated from pigpio to PCA9685 / adafruit_servokit for
Raspberry Pi 5 compatibility.
"""

import time, random
from adafruit_servokit import ServoKit

# === KONFIG ===
SERVO_CHANNEL = 0       # PCA9685 kanal (0-15)
CLOSE_DEG = 6           # dine verdier
OPEN_DEG  = 102
TRIM_DEG  = 0

# Snakk-innstillinger
TALK_MS     = 5000      # hvor lenge den "snakker" pr runde
PAUSE_MS    = 1500      # pause mellom fraser
JITTER      = 0.25      # 0..0.5 variasjon i åpning
BEAT_MS_MIN = 60        # min varighet pr "stavelse"
BEAT_MS_MAX = 140       # max varighet pr "stavelse"

# Servo-innstillinger (mikrosek)
CLOSE_US_DEFAULT = 900
OPEN_US_DEFAULT  = 2000

# === HJELPEFUNKSJONER ===
def clamp(val, a, b): return max(a, min(b, val))

class Beak:
    def __init__(self, servo_channel, close_deg, open_deg, trim_deg=0,
                 close_us=CLOSE_US_DEFAULT, open_us=OPEN_US_DEFAULT):
        """
        Initialiserer servo via PCA9685
        
        Args:
            servo_channel: PCA9685 kanal nummer (0-15)
            close_deg: Grader for lukket posisjon
            open_deg: Grader for åpen posisjon
            trim_deg: Justering av posisjon
            close_us: Pulsewidth for lukket (mikrosekunder)
            open_us: Pulsewidth for åpen (mikrosekunder)
        """
        try:
            # Initialiser PCA9685 (16 kanaler)
            # Standard I2C (GPIO 2/3) på /dev/i2c-1
            self.kit = ServoKit(channels=16)
            self.servo_channel = servo_channel
            
            # Sett pulse width range basert på dine verdier
            self.kit.servo[servo_channel].set_pulse_width_range(close_us, open_us)
            
            self.close_deg = close_deg
            self.open_deg  = open_deg
            self.trim_deg  = trim_deg
            
            self.close_us = close_us
            self.open_us  = open_us
            
            # Start i lukket posisjon
            self.current_deg = self.close_deg + self.trim_deg
            self.kit.servo[servo_channel].angle = self.current_deg
            
            print(f"Servo initialisert på PCA9685 kanal {servo_channel}, posisjon: {self.current_deg}°")
        except Exception as e:
            raise RuntimeError(f"Kunne ikke initialisere PCA9685: {e}\nSjekk at PCA9685 er koblet til I2C (SDA=GPIO2, SCL=GPIO3)")

    def _deg_to_angle(self, deg):
        """Konverterer grader til servo angle"""
        return clamp(deg, 0, 180)

    def goto_deg_smooth(self, target_deg, step_deg=5, dt=0.01):
        """Beveger servo smootht til target grader"""
        target_deg = clamp(target_deg, 0, 180)
        
        while abs(self.current_deg - target_deg) > 1:
            direction = 1 if target_deg > self.current_deg else -1
            step = min(step_deg, abs(target_deg - self.current_deg))
            self.current_deg += direction * step
            self.kit.servo[self.servo_channel].angle = self._deg_to_angle(self.current_deg)
            time.sleep(dt)

    def open_pct(self, pct):
        """Åpner nebbet til en prosentandel (0.0 = lukket, 1.0 = fullt åpen)"""
        pct = clamp(pct, 0.0, 1.0)
        target_deg = self.close_deg + self.trim_deg + pct * (self.open_deg - self.close_deg)
        self.current_deg = target_deg
        self.kit.servo[self.servo_channel].angle = self._deg_to_angle(target_deg)

    def close(self):
        """Lukker nebbet smootht"""
        self.goto_deg_smooth(self.close_deg + self.trim_deg, step_deg=5, dt=0.01)

    def stop(self):
        """Frigjør servo (stopper signaler)"""
        try:
            # Sett servo til None for å frigjøre
            self.kit.servo[self.servo_channel].angle = None
        except:
            pass


def snakk_syklus(beak: Beak, ms: int):
    """Simulerer snakking ved å åpne/lukke nebbet i en periode"""
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        # Velg åpning 30–100% med litt jitter
        base = 0.30 + 0.70 * random.random()
        amt  = clamp(base + (random.uniform(-1, 1) * (JITTER * 2.0)), 0.0, 1.0)

        beak.open_pct(amt)
        time.sleep(random.uniform(BEAT_MS_MIN, BEAT_MS_MAX) / 1000.0)

        # Lukk litt mellom stavelser (ikke helt)
        beak.open_pct(0.12)
        time.sleep(random.uniform(0.040, 0.090))
    beak.open_pct(0.0)

def main():
    """Test-funksjon for å kjøre nebbet standalone"""
    beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
    try:
        print("Tester nebb-bevegelse (Ctrl+C for å avslutte)")
        while True:
            snakk_syklus(beak, TALK_MS)
            time.sleep(PAUSE_MS / 1000.0)
    except KeyboardInterrupt:
        print("\nStopper...")
    finally:
        beak.close()
        beak.stop()

if __name__ == "__main__":
    main()
