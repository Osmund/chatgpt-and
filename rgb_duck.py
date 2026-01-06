from gpiozero import RGBLED
from time import sleep
import threading

# Sett opp RGB LED med Monk Makes (common cathode)
led = RGBLED(red=17, green=27, blue=22, active_high=True)
_blink_thread = None
_blink_stop = threading.Event()

def set_blue():
    stop_blink()
    led.color = (0, 0, 1)  # Blå

def set_red():
    stop_blink()
    led.color = (1, 0, 0)  # Rød

def set_green():
    stop_blink()
    led.color = (0, 1, 0)  # Grønn

def set_yellow():
    stop_blink()
    led.color = (1, 1, 0)  # Gul

def off():
    stop_blink()
    led.off()

def blink_yellow():
    stop_blink()
    def _blink():
        while not _blink_stop.is_set():
            led.color = (1, 1, 0)  # Gul
            sleep(0.3)
            led.off()
            sleep(0.3)
    global _blink_thread
    _blink_stop.clear()
    _blink_thread = threading.Thread(target=_blink, daemon=True)
    _blink_thread.start()

def blink_yellow_purple():
    stop_blink()
    def _blink():
        while not _blink_stop.is_set():
            led.color = (1, 1, 0)  # Gul
            sleep(0.3)
            led.color = (1, 0, 1)  # Lilla
            sleep(0.3)
    global _blink_thread
    _blink_stop.clear()
    _blink_thread = threading.Thread(target=_blink, daemon=True)
    _blink_thread.start()

def stop_blink():
    global _blink_thread
    _blink_stop.set()
    if _blink_thread and _blink_thread.is_alive():
        _blink_thread.join()  # Fjern timeout for å vente til tråden er ferdig

def set_intensity(intensity):
    """Setter LED-intensitet basert på lydnivå (0.0-1.0)"""
    stop_blink()
    # Bruk rød med varierende intensitet
    led.color = (intensity, 0, 0)
    _blink_thread = None