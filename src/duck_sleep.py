"""
Sleep Mode Manager for Duck Assistant

Håndterer sleep mode state for å forhindre falske wake words under filmer osv.
State persisteres til JSON fil for å overleve restarts.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Path til state fil
STATE_FILE = Path(__file__).parent.parent / "sleep_mode.json"


class SleepModeManager:
    """Manager for sleep mode state"""
    
    def __init__(self):
        self._last_load_time = 0  # Timestamp for last file read
        self._cache_duration = 5.0  # Cache state for 5 seconds
        self._load_state()
    
    def _load_state(self, force: bool = False) -> None:
        """
        Laster sleep mode state fra fil (med caching)
        
        Args:
            force: Tving reload fra fil, ignorer cache
        """
        import time
        current_time = time.time()
        
        # Skip reload hvis cache er fersk (unntatt force reload)
        if not force and (current_time - self._last_load_time) < self._cache_duration:
            return
        
        self._last_load_time = current_time
        
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', False)
                    end_time_str = data.get('end_time')
                    if end_time_str:
                        self.end_time = datetime.fromisoformat(end_time_str)
                    else:
                        self.end_time = None
                    self.duration_minutes = data.get('duration_minutes', 0)
                    
                    # Sjekk om sleep mode har utløpt
                    if self.enabled and self.end_time and datetime.now() >= self.end_time:
                        logger.info(f"Sleep mode har utløpt (var til {self.end_time})")
                        self.disable_sleep()
            else:
                self.enabled = False
                self.end_time = None
                self.duration_minutes = 0
        except Exception as e:
            logger.error(f"Feil ved lasting av sleep mode state: {e}")
            self.enabled = False
            self.end_time = None
            self.duration_minutes = 0
    
    def _save_state(self) -> None:
        """Lagrer sleep mode state til fil"""
        try:
            data = {
                'enabled': self.enabled,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration_minutes': self.duration_minutes
            }
            print(f"💾 Lagrer sleep state til {STATE_FILE}: enabled={self.enabled}, duration={self.duration_minutes}", flush=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Sleep state lagret OK", flush=True)
            
            # Force reload for å oppdatere cache
            import time
            self._last_load_time = 0
            
        except Exception as e:
            print(f"❌ FEIL ved lagring av sleep mode state: {e}", flush=True)
            logger.error(f"Feil ved lagring av sleep mode state: {e}")
    
    def enable_sleep(self, duration_minutes: int) -> Dict[str, Any]:
        """
        Aktiverer sleep mode for angitt varighet
        
        Args:
            duration_minutes: Antall minutter sleep mode skal være aktiv
            
        Returns:
            Dict med status og info om når sleep mode slutter
        """
        if duration_minutes <= 0:
            return {
                'success': False,
                'error': 'Varighet må være større enn 0 minutter'
            }
        
        self.enabled = True
        self.duration_minutes = duration_minutes
        self.end_time = datetime.now() + timedelta(minutes=duration_minutes)
        self._save_state()
        
        # Formater sluttid for logging
        end_time_str = self.end_time.strftime("%H:%M")
        
        print(f"✅ Sleep mode aktivert i {duration_minutes} minutter (til {end_time_str})", flush=True)
        logger.info(f"Sleep mode aktivert i {duration_minutes} minutter (til {end_time_str})")
        
        return {
            'success': True,
            'enabled': True,
            'duration_minutes': duration_minutes,
            'end_time': self.end_time.isoformat(),
            'end_time_formatted': end_time_str
        }
    
    def disable_sleep(self) -> Dict[str, Any]:
        """
        Deaktiverer sleep mode
        
        Returns:
            Dict med status
        """
        was_sleeping = self.enabled
        
        self.enabled = False
        self.end_time = None
        self.duration_minutes = 0
        self._save_state()
        
        if was_sleeping:
            logger.info("Sleep mode deaktivert")
        
        return {
            'success': True,
            'enabled': False,
            'was_sleeping': was_sleeping
        }
    
    def is_sleeping(self) -> bool:
        """
        Sjekker om sleep mode er aktiv
        
        Returns:
            True hvis sleep mode er aktiv, False ellers
        """
        # Re-last state fra fil (cached, max hver 5. sekund)
        self._load_state()
        
        if not self.enabled:
            return False
        
        # Sjekk om sleep mode har utløpt
        if self.end_time and datetime.now() >= self.end_time:
            logger.info(f"Sleep mode har utløpt (var til {self.end_time})")
            self.disable_sleep()
            return False
        
        return True
    
    def get_sleep_status(self) -> Dict[str, Any]:
        """
        Henter status for sleep mode
        
        Returns:
            Dict med detaljert status
        """
        # Re-last state fra fil for å få siste endringer fra andre prosesser
        self._load_state()
        
        # Sjekk først om sleep har utløpt
        is_sleeping = self.is_sleeping()
        
        if not is_sleeping:
            return {
                'enabled': False,
                'is_sleeping': False
            }
        
        # Beregn gjenværende tid
        remaining = self.end_time - datetime.now()
        remaining_minutes = int(remaining.total_seconds() / 60)
        
        return {
            'enabled': True,
            'is_sleeping': True,
            'end_time': self.end_time.isoformat(),
            'end_time_formatted': self.end_time.strftime("%H:%M"),
            'duration_minutes': self.duration_minutes,
            'remaining_minutes': remaining_minutes
        }


# Global singleton instance
_sleep_manager = None


def get_sleep_manager() -> SleepModeManager:
    """Returnerer global sleep mode manager instance"""
    global _sleep_manager
    if _sleep_manager is None:
        _sleep_manager = SleepModeManager()
    return _sleep_manager


# Convenience funksjoner
def enable_sleep(duration_minutes: int) -> Dict[str, Any]:
    """Aktiverer sleep mode"""
    return get_sleep_manager().enable_sleep(duration_minutes)


def disable_sleep() -> Dict[str, Any]:
    """Deaktiverer sleep mode"""
    return get_sleep_manager().disable_sleep()


def is_sleeping() -> bool:
    """Sjekker om sleep mode er aktiv"""
    return get_sleep_manager().is_sleeping()


def get_sleep_status() -> Dict[str, Any]:
    """Henter sleep mode status"""
    return get_sleep_manager().get_sleep_status()
