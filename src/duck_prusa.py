"""
PrusaLink Local API Integration for Anda
Monitors 3D printer status via local network connection
"""
import requests
import os
import time
import threading
import logging
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PrusaLinkManager:
    """Manages connection to PrusaLink local API"""
    
    def __init__(self):
        self.api_key = os.getenv('PRUSALINK_API_KEY')
        self.host = os.getenv('PRUSALINK_HOST')  # e.g. "192.168.10.100" or "prusa-xl.local"
        
        # Status tracking
        self.last_status = None
        self.last_check = None
        self.last_state = None
        self.print_finished_callback = None
        self.print_failed_callback = None
        
        # Polling thread
        self.polling_thread = None
        self.stop_polling = False
    
    def is_configured(self) -> bool:
        """Check if PrusaLink is properly configured"""
        return bool(self.api_key and self.host)
    
    def get_printer_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current printer status from PrusaLink local API
        
        Returns:
            {
                'state': 'IDLE' | 'PRINTING' | 'PAUSED' | 'FINISHED' | 'STOPPED' | 'ERROR',
                'progress': 0-100,
                'time_remaining': seconds,
                'time_printing': seconds,
                'job_name': 'filename.gcode',
                'temp_nozzle': 215.0,
                'temp_bed': 60.0
            }
        """
        if not self.is_configured():
            return None
        
        try:
            headers = {
                'X-Api-Key': self.api_key
            }
            
            # PrusaLink API endpoints
            status_url = f"http://{self.host}/api/v1/status"
            job_url = f"http://{self.host}/api/v1/job"
            
            status_response = requests.get(status_url, headers=headers, timeout=5)
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                # PrusaLink combines printer and job info in /status endpoint
                printer = status_data.get('printer', {})
                job = status_data.get('job', {})
                
                # Map printer state to our format
                state_map = {
                    'IDLE': 'IDLE',
                    'BUSY': 'PRINTING',
                    'PRINTING': 'PRINTING',
                    'PAUSED': 'PAUSED',
                    'FINISHED': 'FINISHED',
                    'STOPPED': 'STOPPED',
                    'ERROR': 'ERROR',
                    'ATTENTION': 'ERROR',
                    'READY': 'IDLE'
                }
                
                raw_state = printer.get('state', 'UNKNOWN')
                mapped_state = state_map.get(raw_state, 'UNKNOWN')
                
                # Try to get full job info for file name
                file_info = {}
                job_name = 'ukjent fil'
                if job:
                    try:
                        job_response = requests.get(job_url, headers=headers, timeout=5)
                        if job_response.status_code == 200:
                            job_full = job_response.json()
                            file_info = job_full.get('file', {})
                            raw_name = file_info.get('display_name') or file_info.get('name') or 'ukjent fil'
                            # Clean up job name: remove extension, replace + and _ with spaces
                            job_name = raw_name.replace('.bgcode', '').replace('.gcode', '').replace('+', ' ').replace('_', ' ')
                            # Truncate at next space after 25 chars to avoid cutting words
                            if len(job_name) > 25:
                                # Find next space after position 25
                                next_space = job_name.find(' ', 25)
                                if next_space != -1:
                                    job_name = job_name[:next_space] + '...'
                                else:
                                    job_name = job_name[:22] + '...'
                    except:
                        pass
                
                status = {
                    'state': mapped_state,
                    'progress': job.get('progress', 0),
                    'time_remaining': job.get('time_remaining'),
                    'time_printing': job.get('time_printing'),
                    'job_name': job_name,
                    'temp_nozzle': printer.get('temp_nozzle'),
                    'temp_bed': printer.get('temp_bed')
                }
                
                self.last_status = status
                self.last_check = datetime.now()
                return status
            else:
                logger.warning(f"⚠️ PrusaLink API error: {status_response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Cannot connect to PrusaLink at {self.host}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting PrusaLink status: {e}")
            return None
    
    def get_human_readable_status(self, status: Optional[Dict] = None) -> str:
        """Get status in human-readable Norwegian format"""
        if status is None:
            status = self.get_printer_status()
        
        if not status:
            return "Jeg kan ikke nå printeren akkurat nå. Sjekk at den er på og koblet til nettverket."
        
        state = status['state']
        progress = status.get('progress', 0)
        time_remaining = status.get('time_remaining')
        job_name = status.get('job_name', 'ukjent fil')
        temp_nozzle = status.get('temp_nozzle')
        temp_bed = status.get('temp_bed')
        
        if state == 'IDLE':
            return "Printeren er klar og venter på ny jobb."
        
        elif state == 'PRINTING':
            msg = f"Printeren holder på med '{job_name}'. "
            msg += f"Den er {progress:.0f}% ferdig. "
            
            if time_remaining:
                hours = int(time_remaining // 3600)
                minutes = int((time_remaining % 3600) // 60)
                if hours > 0:
                    msg += f"Estimert {hours} timer og {minutes} minutter igjen. "
                else:
                    msg += f"Estimert {minutes} minutter igjen. "
            
            if temp_nozzle and temp_bed:
                msg += f"Nozzle er {temp_nozzle:.0f}°C og bed er {temp_bed:.0f}°C."
            
            return msg
        
        elif state == 'PAUSED':
            msg = f"Printen '{job_name}' er satt på pause ved {progress:.0f}%. "
            return msg
        
        elif state == 'FINISHED':
            return f"Printen '{job_name}' er ferdig! Den er klar til å plukkes opp."
        
        elif state == 'STOPPED':
            return f"Printen '{job_name}' ble stoppet ved {progress:.0f}%."
        
        elif state == 'ERROR':
            return "Det ser ut som printeren har møtt en feil. Sjekk skjermen din!"
        
        else:
            return f"Printer status: {state}"
    
    def start_monitoring(self, 
                        on_print_finished: Optional[Callable[[str], None]] = None,
                        on_print_failed: Optional[Callable[[str], None]] = None,
                        poll_interval: int = 60):
        """
        Start background monitoring thread
        
        Args:
            on_print_finished: Callback when print finishes successfully
            on_print_failed: Callback when print fails or is cancelled
            poll_interval: Seconds between status checks (default: 60)
        """
        if not self.is_configured():
            logger.warning("PrusaLink not configured, cannot start monitoring")
            return False
        
        self.print_finished_callback = on_print_finished
        self.print_failed_callback = on_print_failed
        self.stop_polling = False
        
        self.polling_thread = threading.Thread(target=self._monitoring_loop, args=(poll_interval,), daemon=True)
        self.polling_thread.start()
        
        logger.info("🖨️ PrusaLink monitoring started")
        return True
    
    def _monitoring_loop(self, poll_interval: int):
        """Background polling loop"""
        while not self.stop_polling:
            try:
                status = self.get_printer_status()
                
                if status:
                    current_state = status['state']
                    job_name = status.get('job_name', 'ukjent fil')
                    
                    # Detect state changes
                    if self.last_state != current_state:
                        logger.info(f"🖨️ Printer state changed: {self.last_state} → {current_state}")
                        
                        # Print finished successfully
                        if self.last_state == 'PRINTING' and current_state == 'FINISHED':
                            if self.print_finished_callback:
                                self.print_finished_callback(job_name)
                        
                        # Print stopped/failed
                        elif self.last_state == 'PRINTING' and current_state in ['STOPPED', 'ERROR']:
                            if self.print_failed_callback:
                                self.print_failed_callback(job_name)
                        
                        self.last_state = current_state
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            time.sleep(poll_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.stop_polling = True
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        logger.info("🖨️ PrusaLink monitoring stopped")


# Global singleton instance
_prusa_manager = None

def get_prusa_manager() -> PrusaLinkManager:
    """Get global PrusaLinkManager instance"""
    global _prusa_manager
    if _prusa_manager is None:
        _prusa_manager = PrusaLinkManager()
    return _prusa_manager
