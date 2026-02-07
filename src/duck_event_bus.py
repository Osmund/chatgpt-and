"""
DuckEventBus — Thread-safe event queue for inter-thread communication.

Erstatter /tmp/duck_*_announcement.txt-filer med queue.Queue.
Hver melding konsumeres nøyaktig én gang — ingen race conditions,
ingen tapte meldinger, ingen partial reads.

Bruk:
    from src.duck_event_bus import get_event_bus, Event

    bus = get_event_bus()

    # Skriver (bakgrunnstråder):
    bus.post(Event.SMS_ANNOUNCEMENT, "Du har fått en SMS fra Mamma")
    bus.post(Event.DUCK_MESSAGE, {"announcement": "...", "from_duck": "..."})
    bus.post(Event.PLAY_SONG, {"path": "/path/to/song", "announce": True})

    # Leser (main loop):
    event = bus.get(timeout=0.5)  # Blokkerer maks 0.5s
    if event:
        event_type, data = event
        if event_type == Event.SMS_ANNOUNCEMENT:
            speak(data, ...)

Tverr-prosess (duck-control, wifi-portal):
    POST http://127.0.0.1:5111/event {"type": "message", "data": "tekst"}
"""

import queue
import threading
from enum import Enum, auto
from typing import Any, Optional, Tuple


class Event(Enum):
    """Event-typer som kan sendes via event-bussen."""

    # SMS og meldinger
    SMS_ANNOUNCEMENT = auto()      # str: SMS/MMS notification text
    SMS_RESPONSE = auto()          # str: Auto-reply confirmation text
    DUCK_MESSAGE = auto()          # dict: {announcement, from_duck, message, media_url}
    DUCK_RESPONSE = auto()         # dict: {response, to_duck}

    # Innhold og underholdning
    PLAY_SONG = auto()             # dict: {path: str, announce: bool}
    SONG_ANNOUNCEMENT = auto()     # str: Boredom song announcement text

    # System-hendelser
    HUNGER_ANNOUNCEMENT = auto()   # str: Hunger notification text
    HUNGER_FED = auto()            # str: Fed-from-panel acknowledgment
    PRUSA_ANNOUNCEMENT = auto()    # str: 3D printer notification
    HOTSPOT_ANNOUNCEMENT = auto()  # str: WiFi hotspot status
    REMINDER = auto()              # dict: {announcement, reminder_id, is_alarm, message}

    # Kontrollpanel-triggere
    EXTERNAL_MESSAGE = auto()      # str: Text from control panel (or '__START_CONVERSATION__')
    SWITCH_NETWORK = auto()        # str: Network switch trigger


class DuckEventBus:
    """
    Thread-safe event bus med prioritert kø.

    Alle events ender i én FIFO-kø som main-loopen konsumerer.
    Hver event leses nøyaktig én gang — ingen dobbelt-lesing,
    ingen tapte meldinger.
    """
    _instance = None
    _create_lock = threading.Lock()

    def __init__(self):
        self._queue: queue.Queue[Tuple[Event, Any]] = queue.Queue()

    @classmethod
    def get_instance(cls) -> 'DuckEventBus':
        if cls._instance is None:
            with cls._create_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def post(self, event_type: Event, data: Any = None):
        """
        Post en event til bussen. Thread-safe, blokkerer aldri.

        Args:
            event_type: Event enum
            data: Vilkårlig data (str, dict, etc.)
        """
        self._queue.put((event_type, data))

    def get(self, timeout: float = 0.5) -> Optional[Tuple[Event, Any]]:
        """
        Hent neste event fra bussen. Blokkerer maks `timeout` sekunder.

        Returns:
            (Event, data) tuple, eller None hvis ingen events i køen.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_nowait(self) -> Optional[Tuple[Event, Any]]:
        """
        Hent neste event uten å blokkere.

        Returns:
            (Event, data) tuple, eller None hvis køen er tom.
        """
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def drain(self, max_events: int = 50) -> list:
        """
        Tøm køen og returner alle ventende events (maks `max_events`).
        Nyttig for batch-prosessering.
        """
        events = []
        for _ in range(max_events):
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    @property
    def pending(self) -> int:
        """Antall events som venter i køen."""
        return self._queue.qsize()

    def clear(self):
        """Tøm køen (brukes ved oppstart for å rydde stale events)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


def get_event_bus() -> DuckEventBus:
    """Hent singleton DuckEventBus-instansen."""
    return DuckEventBus.get_instance()
