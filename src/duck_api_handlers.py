"""
Duck API Handlers
Handles all API endpoints for the Duck control panel.
"""
import json
import os
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class DuckAPIHandlers:
    """API endpoint handlers for Duck control panel"""
    
    def __init__(self, services):
        """
        Initialize API handlers with services.
        
        Args:
            services: ServiceManager instance
        """
        self.services = services
        self.project_root = Path(__file__).parent.parent
        self.db_path = self.project_root / 'duck_memory.db'
    
    def handle_status(self) -> Dict[str, Any]:
        """Get all current settings for status display"""
        try:
            # Read from temp files (TMP config pattern)
            personality = self._read_temp_file('duck_personality.txt', 'normal')
            voice = self._read_temp_file('duck_voice.txt', 'nb-NO-FinnNeural')
            volume = int(self._read_temp_file('duck_volume.txt', '50'))
            beak = self._read_temp_file('duck_beak.txt', 'on')
            speed = int(self._read_temp_file('duck_speed.txt', '50'))
            
            return {
                'personality': personality,
                'voice': voice,
                'volume': volume,
                'beak': beak,
                'speed': speed
            }
        except Exception as e:
            return {
                'personality': 'normal',
                'voice': 'nb-NO-FinnNeural',
                'volume': 50,
                'beak': 'on',
                'speed': 50,
                'error': str(e)
            }
    
    def handle_duck_status(self) -> Dict[str, Any]:
        """Check if chatgpt-duck service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'chatgpt-duck.service'],
                capture_output=True, text=True, timeout=5
            )
            running = result.stdout.strip() == 'active'
            return {'running': running}
        except Exception as e:
            return {'running': False, 'error': str(e)}
    
    def handle_ha_status(self) -> Dict[str, Any]:
        """Check Home Assistant availability (local and cloud) - only for Samantha"""
        try:
            import requests
            from dotenv import load_dotenv
            load_dotenv()
            
            # Only Samantha has Home Assistant
            duck_name = os.getenv('DUCK_NAME', '').lower()
            if duck_name != 'samantha':
                return {'available': False, 'error': 'Home Assistant kun tilgjengelig for Samantha'}
            
            HA_LOCAL_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
            HA_CLOUD_URL = os.getenv("HA_CLOUD_URL", "")
            HA_TOKEN = os.getenv("HA_TOKEN")
            
            if not HA_TOKEN:
                return {'available': False, 'error': 'HA_TOKEN ikke konfigurert'}
            
            # Try local first
            try:
                r = requests.get(
                    f"{HA_LOCAL_URL}/api/",
                    headers={"Authorization": f"Bearer {HA_TOKEN}"},
                    timeout=3
                )
                if r.status_code == 200:
                    return {'available': True, 'url': HA_LOCAL_URL, 'mode': 'local'}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                # Fallback to cloud
                if HA_CLOUD_URL:
                    try:
                        r = requests.get(
                            f"{HA_CLOUD_URL}/api/",
                            headers={"Authorization": f"Bearer {HA_TOKEN}"},
                            timeout=10
                        )
                        if r.status_code == 200:
                            return {'available': True, 'url': HA_CLOUD_URL, 'mode': 'cloud'}
                    except Exception:
                        pass
                return {'available': False, 'error': 'Lokal og cloud ikke tilgjengelig'}
            
            return {'available': False, 'error': 'Ukjent feil'}
            
        except Exception as e:
            return {'available': False, 'error': f'Config error: {str(e)}'}
    
    def handle_duck_location(self) -> Dict[str, Any]:
        """Get Duck's current location from profile_facts or default by DUCK_NAME"""
        try:
            # Check database first
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute("SELECT value FROM profile_facts WHERE key = 'duck_current_location'")
            row = c.fetchone()
            conn.close()
            
            if row:
                return {'location': row[0]}
            
            # Fallback to default location based on DUCK_NAME
            duck_name = os.getenv('DUCK_NAME', '').lower()
            default_locations = {
                'samantha': 'Sokndal (Åmot)',
                'seven': 'Stavanger (Hundvåg)'
            }
            
            location = default_locations.get(duck_name, 'Ukjent')
            return {'location': location}
            
        except Exception as e:
            return {'location': 'Feil', 'error': str(e)}
    
    def handle_boredom_status(self) -> Dict[str, Any]:
        """Get boredom level from database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute("SELECT current_level, last_check FROM boredom_state WHERE id = 1")
            row = c.fetchone()
            conn.close()
            
            if row:
                level, last_check = row
                return {
                    'level': round(level, 1),
                    'last_check': last_check,
                    'status': 'bored' if level >= 7 else 'ok'
                }
            else:
                return {'level': 0, 'status': 'unknown'}
        except Exception as e:
            return {'level': 0, 'error': str(e)}
    
    def handle_hunger_status(self) -> Dict[str, Any]:
        """Get hunger level from database"""
        try:
            hunger_manager = self.services.get_hunger_manager()
            level = hunger_manager.get_hunger_level()
            is_hungry = hunger_manager.is_hungry()
            
            return {
                'level': round(level, 1),
                'status': 'hungry' if is_hungry else 'fed',
                'max': 10
            }
        except Exception as e:
            return {'level': 0, 'error': str(e)}
    
    def handle_vision_status(self) -> Dict[str, Any]:
        """Get Duck-Vision connection status by checking active MQTT clients"""
        try:
            # Check Mosquitto logs for active samantha-vision-client
            result = subprocess.run(
                ['sudo', 'tail', '-100', '/var/log/mosquitto/mosquitto.log'],
                capture_output=True, text=True, timeout=2
            )
            
            if result.returncode == 0:
                # Look for recent samantha-vision-client connection (within last 50 lines)
                lines = result.stdout.strip().split('\n')[-50:]
                
                # Check if samantha-vision-client is connected and not immediately disconnected
                connected_recently = False
                for i, line in enumerate(lines):
                    if 'samantha-vision-client' in line and 'connected from 127.0.0.1' in line:
                        # Check if next few lines show it's still connected (no immediate "closed")
                        disconnect_found = False
                        for j in range(i+1, min(i+3, len(lines))):
                            if 'samantha-vision-client' in lines[j] and 'closed' in lines[j]:
                                disconnect_found = True
                                break
                        if not disconnect_found:
                            connected_recently = True
                
                if connected_recently:
                    return {
                        'connected': True,
                        'status': 'connected',
                        'message': 'Duck-Vision tilkoblet'
                    }
                else:
                    return {
                        'connected': False,
                        'status': 'disconnected',
                        'message': 'Duck-Vision ikke tilkoblet'
                    }
            else:
                return {
                    'connected': False,
                    'status': 'unknown',
                    'message': 'Kunne ikke lese Mosquitto logs'
                }
        except Exception as e:
            return {
                'connected': False,
                'status': 'error',
                'error': str(e),
                'message': f'Feil: {str(e)}'
            }
    
    def handle_feed(self, food_type: str) -> Dict[str, Any]:
        """Feed Anda with food from control panel"""
        try:
            hunger_manager = self.services.get_hunger_manager()
            result = hunger_manager.feed(food_type)
            
            # Create announcement file so Anda says thank you
            if result.get('status') == 'fed':
                announcement = f"Takk for maten! Nam nam! {result['food']}🦆"
                with open('/tmp/duck_hunger_fed.txt', 'w', encoding='utf-8') as f:
                    f.write(announcement)
            
            return result
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def handle_logs(self, lines: int = 50) -> Dict[str, Any]:
        """Get recent logs from chatgpt-duck service"""
        try:
            result = subprocess.run(
                ['journalctl', '-u', 'chatgpt-duck.service', '-n', str(lines), '--no-pager'],
                capture_output=True, text=True, timeout=10
            )
            return {'logs': result.stdout}
        except Exception as e:
            return {'logs': '', 'error': str(e)}
    
    def handle_current_model(self) -> Dict[str, Any]:
        """Get current OpenAI model"""
        model = self._read_temp_file('duck_model.txt', 'gpt-4o-mini')
        return {'model': model}
    
    def handle_available_models(self) -> Dict[str, Any]:
        """Get list of available OpenAI models"""
        models = [
            {'id': 'gpt-4o', 'name': 'GPT-4o (Newest, smartest)'},
            {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini (Fast, cheap)'},
            {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo'},
            {'id': 'gpt-4', 'name': 'GPT-4'},
            {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo (Legacy)'}
        ]
        return {'models': models}
    
    def handle_current_personality(self) -> Dict[str, Any]:
        """Get current personality"""
        personality = self._read_temp_file('duck_personality.txt', 'normal')
        return {'personality': personality}
    
    def handle_current_voice(self) -> Dict[str, Any]:
        """Get current TTS voice"""
        from src.duck_config import DEFAULT_VOICE
        voice = self._read_temp_file('duck_voice.txt', DEFAULT_VOICE)
        return {'voice': voice}
    
    def handle_current_beak(self) -> Dict[str, Any]:
        """Get current beak setting"""
        beak = self._read_temp_file('duck_beak.txt', 'on')
        return {'beak': beak}
    
    def handle_current_speed(self) -> Dict[str, Any]:
        """Get current TTS speed"""
        speed = int(self._read_temp_file('duck_speed.txt', '50'))
        return {'speed': speed}
    
    def handle_current_volume(self) -> Dict[str, Any]:
        """Get current volume"""
        volume = int(self._read_temp_file('duck_volume.txt', '50'))
        return {'volume': volume}
    
    def handle_wake_words(self) -> Dict[str, Any]:
        """Get list of wake words"""
        wake_words = ['quack quack', 'hey duck', 'samantha']
        return {'wake_words': wake_words}
    
    def handle_get_sensitivity(self) -> Dict[str, Any]:
        """Get current wake word sensitivity"""
        try:
            sensitivity_file = self.project_root / 'wake_word_sensitivity.txt'
            if sensitivity_file.exists():
                with open(sensitivity_file, 'r') as f:
                    sensitivity = float(f.read().strip())
            else:
                sensitivity = 0.9  # Default from duck_speech.py
            return {'sensitivity': sensitivity}
        except Exception as e:
            return {'sensitivity': 0.9, 'error': str(e)}
    
    def handle_set_sensitivity(self, sensitivity: float) -> Dict[str, Any]:
        """Set wake word sensitivity (0.0-1.0)"""
        try:
            if not 0.0 <= sensitivity <= 1.0:
                return {'status': 'error', 'message': 'Sensitivity must be between 0.0 and 1.0'}
            
            sensitivity_file = self.project_root / 'wake_word_sensitivity.txt'
            with open(sensitivity_file, 'w') as f:
                f.write(str(sensitivity))
            
            return {'status': 'success', 'message': f'Sensitivity set to {sensitivity}. Restart Anda for changes to take effect.'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def handle_fan_status(self) -> Dict[str, Any]:
        """Get fan status"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'fan-control.service'],
                capture_output=True, text=True, timeout=5
            )
            running = result.stdout.strip() == 'active'
            return {'running': running}
        except Exception as e:
            return {'running': False, 'error': str(e)}
    
    def handle_system_stats(self) -> Dict[str, Any]:
        """Get system stats: CPU temp and memory usage"""
        try:
            stats = {}
            
            # Get CPU temperature
            try:
                result = subprocess.run(
                    ['vcgencmd', 'measure_temp'],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    # Output format: "temp=62.8'C"
                    temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
                    stats['cpu_temp'] = float(temp_str)
                else:
                    stats['cpu_temp'] = None
            except Exception as e:
                stats['cpu_temp'] = None
                stats['temp_error'] = str(e)
            
            # Get memory usage
            try:
                result = subprocess.run(
                    ['free', '-m'],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    mem_line = lines[1].split()
                    total = int(mem_line[1])
                    used = int(mem_line[2])
                    available = int(mem_line[6])
                    
                    stats['memory'] = {
                        'total': total,
                        'used': used,
                        'available': available,
                        'used_percent': round((used / total) * 100, 1)
                    }
                else:
                    stats['memory'] = None
            except Exception as e:
                stats['memory'] = None
                stats['memory_error'] = str(e)
            
            return stats
        except Exception as e:
            return {'error': str(e)}
    
    def handle_users_current(self) -> Dict[str, Any]:
        """Get current user"""
        try:
            user_manager = self.services.get_user_manager()
            current_user = user_manager.get_current_user()
            
            return {
                'username': current_user['username'],
                'display_name': current_user['display_name'],
                'relation': current_user['relation']
            }
        except Exception as e:
            return {'error': str(e)}
    
    def handle_users_list(self) -> Dict[str, Any]:
        """Get all users"""
        try:
            user_manager = self.services.get_user_manager()
            users = user_manager.get_all_users()
            current_user = user_manager.get_current_user()
            
            return {
                'users': users,
                'current_user': current_user['username']
            }
        except Exception as e:
            return {'error': str(e)}
    
    def handle_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        try:
            memory_manager = self.services.get_memory_manager()
            stats = memory_manager.get_stats()
            return {'status': 'success', 'stats': stats}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_profile(self) -> Dict[str, Any]:
        """Get all profile facts"""
        try:
            memory_manager = self.services.get_memory_manager()
            facts = memory_manager.get_profile_facts(limit=50)
            facts_list = [
                {
                    'key': f.key,
                    'value': f.value,
                    'topic': f.topic,
                    'confidence': f.confidence,
                    'frequency': f.frequency,
                    'source': f.source,
                    'last_updated': f.last_updated
                }
                for f in facts
            ]
            return {'status': 'success', 'facts': facts_list}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_topics(self) -> Dict[str, Any]:
        """Get topic statistics"""
        try:
            memory_manager = self.services.get_memory_manager()
            topics = memory_manager.get_topic_stats(limit=20)
            return {'status': 'success', 'topics': topics}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_conversations(self) -> Dict[str, Any]:
        """Get recent conversations"""
        try:
            memory_manager = self.services.get_memory_manager()
            conn = memory_manager._get_connection()
            c = conn.cursor()
            
            c.execute("""
                SELECT id, user_text, ai_response, timestamp, session_id
                FROM messages
                ORDER BY timestamp DESC
                LIMIT 20
            """)
            
            conversations = []
            for row in c.fetchall():
                conversations.append({
                    'id': row['id'],
                    'user_text': row['user_text'],
                    'ai_response': row['ai_response'],
                    'timestamp': row['timestamp'],
                    'session_id': row['session_id']
                })
            
            conn.close()
            return {'status': 'success', 'conversations': conversations}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_embedding_status(self) -> Dict[str, Any]:
        """Get embedding statistics"""
        try:
            memory_manager = self.services.get_memory_manager()
            conn = memory_manager._get_connection()
            c = conn.cursor()
            
            # Count memories with embeddings
            c.execute("SELECT COUNT(*) as total FROM memories WHERE embedding IS NOT NULL")
            total_with_embeddings = c.fetchone()['total']
            
            # Count total memories
            c.execute("SELECT COUNT(*) as total FROM memories")
            total_memories = c.fetchone()['total']
            
            conn.close()
            
            percentage = (total_with_embeddings / total_memories * 100) if total_memories > 0 else 0
            
            return {
                'status': 'success',
                'total_memories': total_memories,
                'with_embeddings': total_with_embeddings,
                'percentage': round(percentage, 1)
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_worker_status(self) -> Dict[str, Any]:
        """Get memory worker status"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'duck-memory-worker.service'],
                capture_output=True, text=True, timeout=5
            )
            running = result.stdout.strip() == 'active'
            
            # Get unprocessed messages count
            unprocessed_count = 0
            try:
                memory_manager = self.services.get_memory_manager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM messages WHERE processed = 0")
                unprocessed_count = c.fetchone()[0]
                conn.close()
            except Exception as e:
                print(f"Warning: Could not get unprocessed count: {e}", flush=True)
            
            # Get process stats if running
            if running:
                result = subprocess.run(
                    ['systemctl', 'show', 'duck-memory-worker.service', 
                     '-p', 'CPUUsageNSec', '-p', 'MemoryCurrent'],
                    capture_output=True, text=True, timeout=5
                )
                return {
                    'status': 'success', 
                    'running': True, 
                    'unprocessed': unprocessed_count,
                    'details': result.stdout
                }
            
            return {
                'status': 'success', 
                'running': False,
                'unprocessed': unprocessed_count
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_recent_updates(self) -> Dict[str, Any]:
        """Get recent memory updates"""
        try:
            memory_manager = self.services.get_memory_manager()
            conn = memory_manager._get_connection()
            c = conn.cursor()
            
            c.execute("""
                SELECT text, topic, confidence, source, first_seen
                FROM memories
                ORDER BY first_seen DESC
                LIMIT 15
            """)
            
            updates = []
            for row in c.fetchall():
                updates.append({
                    'text': row['text'],
                    'topic': row['topic'],
                    'confidence': row['confidence'],
                    'source': row['source'],
                    'first_seen': row['first_seen']
                })
            
            conn.close()
            return {'status': 'success', 'updates': updates}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_memory_quick_facts(self) -> Dict[str, Any]:
        """Get quick access facts"""
        try:
            memory_manager = self.services.get_memory_manager()
            facts = memory_manager.get_profile_facts(limit=10)
            
            quick_facts = []
            for f in facts:
                if f.frequency >= 3 or f.confidence >= 0.8:
                    quick_facts.append({
                        'key': f.key,
                        'value': f.value,
                        'confidence': f.confidence,
                        'frequency': f.frequency
                    })
            
            return {'status': 'success', 'facts': quick_facts}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_settings_max_context_facts(self) -> Dict[str, Any]:
        """Get max_context_facts setting"""
        try:
            mm = self.services.get_memory_manager()
            conn = mm._get_connection()
            c = conn.cursor()
            
            c.execute("SELECT value FROM profile_facts WHERE key = 'max_context_facts' LIMIT 1")
            row = c.fetchone()
            max_facts = int(row['value']) if row else 100
            
            conn.close()
            return {'status': 'success', 'max_context_facts': max_facts}
        except Exception as e:
            return {'status': 'error', 'error': str(e), 'max_context_facts': 100}
    
    def handle_settings_memory(self) -> Dict[str, Any]:
        """Get all memory settings"""
        try:
            mm = self.services.get_memory_manager()
            conn = mm._get_connection()
            c = conn.cursor()
            
            settings = {}
            defaults = {
                'embedding_search_limit': 30,
                'memory_limit': 8,
                'memory_threshold': 0.35
            }
            
            for key in defaults.keys():
                c.execute("SELECT value FROM profile_facts WHERE key = ? LIMIT 1", (key,))
                row = c.fetchone()
                if row:
                    settings[key] = float(row['value']) if 'threshold' in key else int(row['value'])
                else:
                    settings[key] = defaults[key]
            
            conn.close()
            return {'status': 'success', **settings}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_personality_get(self) -> Dict[str, Any]:
        """Get current personality"""
        try:
            personality = self._read_temp_file('duck_personality.txt', 'normal')
            return {'status': 'success', 'personality': personality}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def handle_backup_status(self) -> Dict[str, Any]:
        """Get backup status and list of backups"""
        try:
            result = subprocess.run(
                ['rclone', 'lsf', 'anda-backup:duck-backups/Samantha/', '--dirs-only'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                backups = [line.strip('/') for line in result.stdout.strip().split('\n') if line.strip()]
                backups.sort(reverse=True)  # Newest first
                return {
                    'status': 'success',
                    'backups': backups[:10],  # Last 10
                    'total': len(backups),
                    'latest': backups[0] if backups else None
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Kunne ikke hente backups',
                    'backups': [],
                    'total': 0
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'backups': [],
                'total': 0
            }
    
    def handle_backup_start(self) -> Dict[str, Any]:
        """Start a new backup"""
        try:
            result = subprocess.run(
                ['bash', str(self.project_root / 'backup-anda.sh')],
                capture_output=True,
                text=True,
                timeout=120  # 2 min timeout
            )
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'message': 'Backup fullført!',
                    'output': result.stdout
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Backup feilet',
                    'error': result.stderr
                }
        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'message': 'Backup timeout (>2 min)'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    # Helper methods
    
    def handle_printer_status(self) -> Dict[str, Any]:
        """Get 3D printer status from PrusaLink"""
        try:
            from duck_prusa import get_prusa_manager
            prusa = get_prusa_manager()
            
            if not prusa.is_configured():
                return {
                    'status': 'not_configured',
                    'message': 'PrusaLink ikke konfigurert'
                }
            
            printer_status = prusa.get_printer_status()
            
            if not printer_status:
                return {
                    'status': 'error',
                    'message': 'Kunne ikke hente printerstatus'
                }
            
            return {
                'status': 'success',
                'printer': {
                    'state': printer_status['state'],
                    'progress': printer_status.get('progress', 0),
                    'time_remaining': printer_status.get('time_remaining'),
                    'time_printing': printer_status.get('time_printing'),
                    'job_name': printer_status.get('job_name', 'Ingen jobb'),
                    'temp_nozzle': printer_status.get('temp_nozzle'),
                    'temp_bed': printer_status.get('temp_bed')
                },
                'human_readable': prusa.get_human_readable_status(printer_status)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Feil: {str(e)}'
            }
    
    def _read_temp_file(self, filename: str, default: str = '') -> str:
        """Read value from /tmp file"""
        filepath = Path('/tmp') / filename
        try:
            if filepath.exists():
                with open(filepath, 'r') as f:
                    content = f.read().strip()
                    return content if content else default
        except Exception:
            pass
        return default
