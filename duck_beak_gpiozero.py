#!/usr/bin/env python3
import time, random
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory

# === KONFIG ===
GPIO_SERVO = 12         # PWM-pin til servo (GPIO12 - software PWM fungerer med I2S)
CLOSE_DEG = 6            # dine verdier
OPEN_DEG  = 102
TRIM_DEG  = 0

# Snakk-innstillinger
TALK_MS     = 5000       # hvor lenge den "snakker" pr runde
PAUSE_MS    = 1500       # pause mellom fraser
JITTER      = 0.25       # 0..0.5 variasjon i åpning
BEAT_MS_MIN = 60         # min varighet pr "stavelse"
BEAT_MS_MAX = 140        # max varighet pr "stavelse"

# Servo-innstillinger
# gpiozero bruker verdier fra -1 (min) til +1 (max)
# Vi mapper fra grader til dette
CLOSE_US_DEFAULT = 900
OPEN_US_DEFAULT  = 2000

# === HJELPEFUNKSJONER ===
def clamp(val, a, b): return max(a, min(b, val))

class Beak:
    def __init__(self, gpio, close_deg, open_deg, trim_deg=0,
                 close_us=CLOSE_US_DEFAULT, open_us=OPEN_US_DEFAULT):
        self.gpio = gpio
        self.close_deg = close_deg
        self.open_deg  = open_deg
        self.trim_deg  = trim_deg
        
        # Bruk software PWM factory (fungerer med I2S)
        try:
            # Prøv pigpio factory først (best presisjon)
            factory = PiGPIOFactory()
            self.servo = Servo(
                gpio,
                min_pulse_width=close_us/1000000,  # convert to seconds
                max_pulse_width=open_us/1000000,
                pin_factory=factory
            )
        except:
            # Fallback til standard software PWM
            self.servo = Servo(
                gpio,
                min_pulse_width=close_us/1000000,
                max_pulse_width=open_us/1000000
            )
        
        # Start i lukket posisjon
        self.current_value = -1  # -1 = closed
        self.servo.value = self.current_value

    def _deg_to_servo_value(self, deg):
        """Konverter grader (0-180) til servo value (-1 til +1)"""
        deg = clamp(deg, 0, 180)
        # Map fra close_deg..open_deg til -1..+1
        if self.open_deg == self.close_deg:
            return 0
        normalized = (deg - self.close_deg) / (self.open_deg - self.close_deg)
        return (normalized * 2) - 1  # Map 0..1 to -1..+1

    def goto_deg_smooth(self, target_deg, step_deg=5, dt=0.01):
        target_deg = clamp(target_deg, 0, 180)
        target_value = self._deg_to_servo_value(target_deg)
        
        # Smooth transition
        steps = 10
        step_size = (target_value - self.current_value) / steps
        
        for _ in range(steps):
            self.current_value += step_size
            self.servo.value = clamp(self.current_value, -1, 1)
            time.sleep(dt / steps)
        
        self.current_value = target_value
        self.servo.value = clamp(self.current_value, -1, 1)

    def open_pct(self, pct):
        pct = clamp(pct, 0.0, 1.0)
        target_deg = self.close_deg + self.trim_deg + pct * (self.open_deg - self.close_deg)
        target_value = self._deg_to_servo_value(target_deg)
        self.current_value = target_value
        self.servo.value = clamp(self.current_value, -1, 1)

    def close(self):
        self.goto_deg_smooth(self.close_deg + self.trim_deg, step_deg=5, dt=0.01)

    def stop(self):
        self.servo.close()

def snakk_syklus(beak: Beak, ms: int):
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
    beak = Beak(GPIO_SERVO, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
    try:
        while True:
            snakk_syklus(beak, TALK_MS)
            time.sleep(PAUSE_MS / 1000.0)
    except KeyboardInterrupt:
        pass
    finally:
        beak.close()
        beak.stop()

if __name__ == "__main__":
    main()
