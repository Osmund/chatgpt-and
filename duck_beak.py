#!/usr/bin/env python3
import time, random
import pigpio

# === KONFIG ===
GPIO_SERVO = 12         # PWM-pin til servo
CLOSE_DEG = 6            # dine verdier
OPEN_DEG  = 102
TRIM_DEG  = 0

# Snakk-innstillinger
TALK_MS     = 5000       # hvor lenge den "snakker" pr runde
PAUSE_MS    = 1500       # pause mellom fraser
JITTER      = 0.25       # 0..0.5 variasjon i åpning
BEAT_MS_MIN = 60         # min varighet pr "stavelse"
BEAT_MS_MAX = 140        # max varighet pr "stavelse"

# Servo-innstillinger (mikrosek)
CLOSE_US_DEFAULT = 900
OPEN_US_DEFAULT  = 2000

# === HJELPEFUNKSJONER ===
def clamp(val, a, b): return max(a, min(b, val))

class Beak:
    def __init__(self, gpio, close_deg, open_deg, trim_deg=0,
                 close_us=CLOSE_US_DEFAULT, open_us=OPEN_US_DEFAULT):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("pigpio daemon kjører ikke. Start med: sudo systemctl start pigpio")

        self.gpio = gpio
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)

        self.close_deg = close_deg
        self.open_deg  = open_deg
        self.trim_deg  = trim_deg

        self.close_us = close_us
        self.open_us  = open_us

        # Bruk hardware_PWM hvis tilgjengelig, ellers wave
        self.current_us = self._deg_to_us(self.close_deg + self.trim_deg)
        self._set_position(self.current_us)
        print(f"Servo initialisert på GPIO {self.gpio}, pulsewidth: {self.current_us}us")

    def _set_position(self, pulsewidth_us):
        """Setter servo-posisjon med wave-basert PWM (fungerer alltid)"""
        # Stopp eventuell eksisterende wave
        self.pi.wave_clear()
        
        # Lag en PWM-puls (20ms periode = 50Hz)
        frequency = 50  # Hz
        period_us = 1000000 // frequency  # 20000 us
        
        # Lag pulsen: HIGH i pulsewidth_us, LOW resten
        waveform = []
        waveform.append(pigpio.pulse(1 << self.gpio, 0, pulsewidth_us))
        waveform.append(pigpio.pulse(0, 1 << self.gpio, period_us - pulsewidth_us))
        
        self.pi.wave_add_generic(waveform)
        wave_id = self.pi.wave_create()
        
        if wave_id >= 0:
            # Send wave kontinuerlig
            self.pi.wave_send_repeat(wave_id)

    def _deg_to_us(self, deg):
        deg = clamp(deg, 0, 180)
        span_deg = 180.0
        span_us  = (self.open_us - self.close_us)
        return int(self.close_us + (deg / span_deg) * span_us)

    def goto_deg_smooth(self, target_deg, step_deg=5, dt=0.01):
        target_deg = clamp(target_deg, 0, 180)
        target_us = self._deg_to_us(target_deg)
        while abs(self.current_us - target_us) > 5:
            direction = 1 if target_us > self.current_us else -1
            step_us = abs(self._deg_to_us(step_deg) - self._deg_to_us(0))
            self.current_us += direction * min(step_us, abs(target_us - self.current_us))
            self._set_position(self.current_us)
            time.sleep(dt)

    def open_pct(self, pct):
        pct = clamp(pct, 0.0, 1.0)
        target_deg = self.close_deg + self.trim_deg + pct * (self.open_deg - self.close_deg)
        target_us = self._deg_to_us(target_deg)
        self.current_us = target_us
        self._set_position(self.current_us)

    def close(self):
        self.goto_deg_smooth(self.close_deg + self.trim_deg, step_deg=5, dt=0.01)

    def stop(self):
        # Stopp wave og slipp pin
        self.pi.wave_tx_stop()
        self.pi.wave_clear()
        self.pi.write(self.gpio, 0)
        self.pi.stop()

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
