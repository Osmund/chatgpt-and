#!/usr/bin/env python3
"""
Web-kontrollpanel for ChatGPT Duck
Kjører på port 3000 for å starte/stoppe anda-servicen

REFAKTORERT: Bruker eksterne templates (HTML/CSS/JS)
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from src.duck_memory import MemoryManager
from src.duck_user_manager import UserManager

# Template directory
TEMPLATE_DIR = Path(__file__).parent / 'templates'


def load_template(filename):
    """Last template-fil fra templates/ mappen"""
    filepath = TEMPLATE_DIR / filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Template ikke funnet: {filepath}")
        return ""


# Legacy compatibility - loads HTML from external file
def get_html_template():
    return load_template('index.html')


class DuckControlHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            html_content = get_html_template()
            self.wfile.write(html_content.encode())
        
        elif self.path == '/style.css':
            self.send_response(200)
            self.send_header('Content-type', 'text/css; charset=utf-8')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            css_content = load_template('style.css')
            self.wfile.write(css_content.encode())
        
        elif self.path == '/app.js':
            self.send_response(200)
            self.send_header('Content-type', 'application/javascript; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            js_content = load_template('app.js')
            self.wfile.write(js_content.encode())
        
        elif self.path == '/favicon.ico':
            # Return 204 No Content for favicon to avoid console errors
            self.send_response(204)
            self.end_headers()
        
        elif self.path == '/status':
            # Hent alle innstillinger for status
            try:
                # Personlighet
                personality_file = '/tmp/duck_personality.txt'
                personality = 'normal'
                if os.path.exists(personality_file):
                    with open(personality_file, 'r') as f:
                        personality = f.read().strip() or 'normal'
                
                # Stemme
                voice_file = '/tmp/duck_voice.txt'
                voice = 'nb-NO-FinnNeural'
                if os.path.exists(voice_file):
                    with open(voice_file, 'r') as f:
                        voice = f.read().strip() or 'nb-NO-FinnNeural'
                
                # Volum
                volume_file = '/tmp/duck_volume.txt'
                volume = 50
                if os.path.exists(volume_file):
                    with open(volume_file, 'r') as f:
                        volume = int(f.read().strip() or '50')
                
                # Nebbet
                beak_file = '/tmp/duck_beak.txt'
                beak = 'on'
                if os.path.exists(beak_file):
                    with open(beak_file, 'r') as f:
                        beak = f.read().strip() or 'on'
                
                # Hastighet
                speed_file = '/tmp/duck_speed.txt'
                speed = 50
                if os.path.exists(speed_file):
                    with open(speed_file, 'r') as f:
                        speed = int(f.read().strip() or '50')
                
                response = {
                    'personality': personality,
                    'voice': voice,
                    'volume': volume,
                    'beak': beak,
                    'speed': speed
                }
            except Exception as e:
                response = {
                    'personality': 'normal',
                    'voice': 'nb-NO-FinnNeural',
                    'volume': 50,
                    'beak': 'on',
                    'speed': 50,
                    'error': str(e)
                }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/duck-status':
            # Sjekk om duck-service kjører
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                running = result.stdout.strip() == 'active'
                response = {'running': running}
            except Exception as e:
                response = {'running': False, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/logs':
            # Hent siste logger
            try:
                result = subprocess.run(
                    ['sudo', 'journalctl', '-u', 'chatgpt-duck.service', '-n', '50', '--no-pager'],
                    capture_output=True, text=True, timeout=5
                )
                response = {'logs': result.stdout}
            except Exception as e:
                response = {'logs': f'Feil ved henting av logger: {e}'}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-model':
            # Hent gjeldende AI-modell
            try:
                from src.duck_config import DEFAULT_MODEL
                model_file = '/tmp/duck_model.txt'
                
                if os.path.exists(model_file):
                    with open(model_file, 'r') as f:
                        model = f.read().strip()
                        if not model:
                            model = DEFAULT_MODEL
                else:
                    model = DEFAULT_MODEL
                
                response = {'model': model}
            except Exception as e:
                response = {'model': 'gpt-4-turbo-2024-04-09', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/available-models':
            # Hent liste over alle tilgjengelige modeller fra config
            try:
                from src.duck_config import AVAILABLE_MODELS, DEFAULT_MODEL
                
                # Konverter til liste for frontend
                models = []
                for model_id, info in AVAILABLE_MODELS.items():
                    models.append({
                        'id': model_id,
                        'name': info['name'],
                        'accuracy': info.get('accuracy', 'N/A'),
                        'latency': info.get('latency', 'N/A'),
                        'cost': info.get('cost', 'N/A'),
                        'is_default': model_id == DEFAULT_MODEL
                    })
                
                response = {'models': models, 'default': DEFAULT_MODEL}
            except Exception as e:
                response = {'models': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-personality':
            # Hent gjeldende personlighet
            try:
                personality_file = '/tmp/duck_personality.txt'
                default_personality = 'normal'
                
                if os.path.exists(personality_file):
                    with open(personality_file, 'r') as f:
                        personality = f.read().strip()
                        if not personality:
                            personality = default_personality
                else:
                    personality = default_personality
                
                response = {'personality': personality}
            except Exception as e:
                response = {'personality': 'normal', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-voice':
            # Hent gjeldende TTS-stemme
            try:
                voice_file = '/tmp/duck_voice.txt'
                default_voice = 'nb-NO-FinnNeural'
                
                if os.path.exists(voice_file):
                    with open(voice_file, 'r') as f:
                        voice = f.read().strip()
                        if not voice:
                            voice = default_voice
                else:
                    voice = default_voice
                
                response = {'voice': voice}
            except Exception as e:
                response = {'voice': 'nb-NO-FinnNeural', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-beak':
            # Hent gjeldende nebbet-status
            try:
                beak_file = '/tmp/duck_beak.txt'
                default_beak = 'on'
                
                if os.path.exists(beak_file):
                    with open(beak_file, 'r') as f:
                        beak = f.read().strip()
                        if not beak:
                            beak = default_beak
                else:
                    beak = default_beak
                
                response = {'beak': beak}
            except Exception as e:
                response = {'beak': 'on', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-speed':
            # Hent gjeldende talehastighet
            try:
                speed_file = '/tmp/duck_speed.txt'
                default_speed = '50'
                
                if os.path.exists(speed_file):
                    with open(speed_file, 'r') as f:
                        speed = f.read().strip()
                        if not speed:
                            speed = default_speed
                else:
                    speed = default_speed
                
                response = {'speed': int(speed)}
            except Exception as e:
                response = {'speed': 50, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-volume':
            # Hent gjeldende volum
            try:
                volume_file = '/tmp/duck_volume.txt'
                default_volume = '50'
                
                if os.path.exists(volume_file):
                    with open(volume_file, 'r') as f:
                        volume = f.read().strip()
                        if not volume:
                            volume = default_volume
                else:
                    volume = default_volume
                
                response = {'volume': int(volume)}
            except Exception as e:
                response = {'volume': 50, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/wake-words':
            # Returner liste over aktive wake words (Porcupine)
            try:
                wake_words = ['Samantha', 'quack quack']
                response = {'wake_words': wake_words}
            except Exception as e:
                response = {'error': str(e), 'wake_words': []}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/fan-status':
            # Hent viftestatus
            try:
                status_file = '/tmp/duck_fan_status.txt'
                if os.path.exists(status_file):
                    with open(status_file, 'r') as f:
                        data = f.read().strip().split('|')
                        if len(data) == 3:
                            response = {
                                'mode': data[0],
                                'running': data[1].lower() == 'true',
                                'temp': float(data[2])
                            }
                        else:
                            response = {'mode': 'auto', 'running': False, 'temp': 0.0}
                else:
                    response = {'mode': 'auto', 'running': False, 'temp': 0.0}
            except Exception as e:
                response = {'mode': 'auto', 'running': False, 'temp': 0.0, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/songs':
            # Hent liste over tilgjengelige sanger
            try:
                music_dir = '/home/admog/Code/chatgpt-and/musikk'
                songs = []
                
                if os.path.exists(music_dir):
                    for artist_song in os.listdir(music_dir):
                        song_path = os.path.join(music_dir, artist_song)
                        if os.path.isdir(song_path):
                            # Sjekk om begge filene finnes
                            mix_file = os.path.join(song_path, 'duck_mix.wav')
                            vocals_file = os.path.join(song_path, 'vocals_duck.wav')
                            if os.path.exists(mix_file) and os.path.exists(vocals_file):
                                songs.append({
                                    'name': artist_song,
                                    'path': song_path
                                })
                
                # Sorter alfabetisk
                songs.sort(key=lambda x: x['name'])
                response = {'songs': songs}
            except Exception as e:
                response = {'songs': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/wifi-networks':
            # Hent tilgjengelige WiFi-nettverk
            try:
                result = subprocess.run(
                    ['sudo', 'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list'],
                    capture_output=True, text=True, timeout=10
                )
                
                networks = []
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                ssid = parts[0]
                                signal = parts[1] if len(parts) > 1 else '0'
                                if ssid and ssid != '--':
                                    networks.append({
                                        'ssid': ssid,
                                        'signal': signal + '%'
                                    })
                
                response = {'status': 'success', 'networks': networks}
            except Exception as e:
                response = {'status': 'error', 'networks': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        # ==================== MEMORY API ====================
        elif self.path == '/api/memory/stats':
            # Get memory system statistics
            try:
                memory_manager = MemoryManager()
                stats = memory_manager.get_stats()
                response = {'status': 'success', 'stats': stats}
            except Exception as e:
                response = {'status': 'error', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/profile':
            # Get all profile facts
            try:
                memory_manager = MemoryManager()
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
                response = {'status': 'success', 'facts': facts_list}
            except Exception as e:
                response = {'status': 'error', 'facts': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path.startswith('/api/memory/memories'):
            # Get memories with optional search
            try:
                memory_manager = MemoryManager()
                query_params = self.path.split('?')[1] if '?' in self.path else ''
                
                # Parse query parameter
                search_query = ''
                if 'q=' in query_params:
                    search_query = query_params.split('q=')[1].split('&')[0]
                    search_query = search_query.replace('+', ' ')
                
                if search_query:
                    # Search memories
                    results = memory_manager.search_memories(search_query, limit=20)
                    memories_list = [
                        {
                            'id': m.id,
                            'text': m.text,
                            'topic': m.topic,
                            'frequency': m.frequency,
                            'confidence': m.confidence,
                            'score': score,
                            'first_seen': m.first_seen,
                            'last_accessed': m.last_accessed
                        }
                        for m, score in results
                    ]
                else:
                    # Get recent memories
                    conn = memory_manager._get_connection()
                    c = conn.cursor()
                    c.execute("""
                        SELECT * FROM memories 
                        ORDER BY last_accessed DESC 
                        LIMIT 20
                    """)
                    memories_list = []
                    for row in c.fetchall():
                        memories_list.append({
                            'id': row['id'],
                            'text': row['text'],
                            'topic': row['topic'],
                            'frequency': row['frequency'],
                            'confidence': row['confidence'],
                            'first_seen': row['first_seen'],
                            'last_accessed': row['last_accessed']
                        })
                    conn.close()
                
                response = {'status': 'success', 'memories': memories_list}
            except Exception as e:
                response = {'status': 'error', 'memories': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/topics':
            # Get topic statistics
            try:
                memory_manager = MemoryManager()
                topics = memory_manager.get_topic_stats(limit=20)
                response = {'status': 'success', 'topics': topics}
            except Exception as e:
                response = {'status': 'error', 'topics': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/conversations':
            # Get recent conversations
            try:
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                # Group messages by date
                c.execute("""
                    SELECT 
                        date(timestamp) as date,
                        COUNT(*) as message_count,
                        MIN(timestamp) as first_msg,
                        MAX(timestamp) as last_msg
                    FROM messages
                    GROUP BY date(timestamp)
                    ORDER BY date DESC
                    LIMIT 30
                """)
                
                conversations = []
                for row in c.fetchall():
                    conversations.append({
                        'date': row['date'],
                        'message_count': row['message_count'],
                        'first_msg': row['first_msg'],
                        'last_msg': row['last_msg']
                    })
                
                conn.close()
                response = {'status': 'success', 'conversations': conversations}
            except Exception as e:
                response = {'status': 'error', 'conversations': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/embedding-status':
            # Get embedding status
            try:
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) as total FROM profile_facts")
                total = c.fetchone()['total']
                
                c.execute("SELECT COUNT(*) as with_embedding FROM profile_facts WHERE embedding IS NOT NULL")
                with_embedding = c.fetchone()['with_embedding']
                
                conn.close()
                response = {
                    'status': 'success',
                    'total_facts': total,
                    'with_embedding': with_embedding,
                    'percentage': round((with_embedding / total * 100) if total > 0 else 0, 1)
                }
            except Exception as e:
                response = {'status': 'error', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/worker-status':
            # Get memory worker status
            try:
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                # Count unprocessed messages
                c.execute("SELECT COUNT(*) as unprocessed FROM messages WHERE processed = 0")
                unprocessed = c.fetchone()['unprocessed']
                
                # Get last processed timestamp
                c.execute("SELECT MAX(timestamp) as last_processed FROM messages WHERE processed = 1")
                last_row = c.fetchone()
                last_processed = last_row['last_processed'] if last_row['last_processed'] else None
                
                # Check if worker service is running
                try:
                    result = subprocess.run(['systemctl', 'is-active', 'duck-memory-worker.service'], 
                                          capture_output=True, text=True, check=False)
                    is_active = result.stdout.strip() == 'active'
                except:
                    is_active = False
                
                conn.close()
                response = {
                    'status': 'success',
                    'is_active': is_active,
                    'unprocessed_messages': unprocessed,
                    'last_processed': last_processed
                }
            except Exception as e:
                response = {'status': 'error', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/recent-updates':
            # Get recently updated facts
            try:
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                c.execute("""
                    SELECT key, value, topic, last_updated
                    FROM profile_facts
                    ORDER BY last_updated DESC
                    LIMIT 10
                """)
                
                updates = []
                for row in c.fetchall():
                    updates.append({
                        'key': row['key'],
                        'value': row['value'],
                        'topic': row['topic'],
                        'last_updated': row['last_updated']
                    })
                
                conn.close()
                response = {'status': 'success', 'updates': updates}
            except Exception as e:
                response = {'status': 'error', 'updates': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/memory/quick-facts':
            # Get most important quick facts
            try:
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                # Get key facts
                quick_facts = {}
                
                # Name
                c.execute("SELECT value FROM profile_facts WHERE key = 'user_name' LIMIT 1")
                row = c.fetchone()
                if row:
                    quick_facts['name'] = row['value']
                else:
                    quick_facts['name'] = 'Ukjent'
                
                # Sisters (only sister_1_name, sister_2_name, sister_3_name exactly)
                c.execute("SELECT key, value FROM profile_facts WHERE key IN ('sister_1_name', 'sister_2_name', 'sister_3_name') ORDER BY key")
                sisters = [row['value'] for row in c.fetchall()]
                quick_facts['sisters'] = sisters
                quick_facts['sisters_count'] = len(sisters)
                
                # Nieces/Nephews
                c.execute("SELECT value FROM profile_facts WHERE key = 'nieces_count' LIMIT 1")
                row = c.fetchone()
                quick_facts['nieces_count'] = int(row['value']) if row else 0
                
                c.execute("SELECT value FROM profile_facts WHERE key = 'nephews_count' LIMIT 1")
                row = c.fetchone()
                quick_facts['nephews_count'] = int(row['value']) if row else 0
                
                conn.close()
                response = {'status': 'success', **quick_facts}
            except Exception as e:
                response = {'status': 'error', 'error': str(e), 'name': 'Ukjent', 'sisters': [], 'sisters_count': 0, 'nieces_count': 0, 'nephews_count': 0}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/settings/max-context-facts':
            # Hent nåværende max_context_facts setting
            try:
                mm = MemoryManager()
                conn = mm._get_connection()
                c = conn.cursor()
                
                c.execute("SELECT value FROM profile_facts WHERE key = 'max_context_facts' LIMIT 1")
                row = c.fetchone()
                max_facts = int(row['value']) if row else 100  # Default 100
                
                conn.close()
                response = {'status': 'success', 'max_context_facts': max_facts}
            except Exception as e:
                response = {'status': 'error', 'error': str(e), 'max_context_facts': 100}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/settings/memory':
            # Hent alle memory settings
            try:
                mm = MemoryManager()
                conn = mm._get_connection()
                c = conn.cursor()
                
                settings = {}
                for key in ['embedding_search_limit', 'memory_limit', 'memory_threshold']:
                    c.execute("SELECT value FROM profile_facts WHERE key = ? LIMIT 1", (key,))
                    row = c.fetchone()
                    if row:
                        settings[key] = float(row['value']) if 'threshold' in key else int(row['value'])
                    else:
                        # Defaults
                        defaults = {'embedding_search_limit': 30, 'memory_limit': 8, 'memory_threshold': 0.35}
                        settings[key] = defaults[key]
                
                conn.close()
                response = {'status': 'success', **settings}
            except Exception as e:
                response = {'status': 'error', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/users/current':
            # Hent nåværende bruker
            try:
                user_manager = UserManager()
                current_user = user_manager.get_current_user()
                
                response = {
                    'username': current_user['username'],
                    'display_name': current_user['display_name'],
                    'relation': current_user['relation']
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        
        elif self.path == '/api/users/list':
            # Hent alle brukere
            try:
                user_manager = UserManager()
                users = user_manager.get_all_users()
                current_user = user_manager.get_current_user()
                
                response = {
                    'users': users,
                    'current_user': current_user['username']
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_DELETE(self):
        """Handle DELETE requests for memory management"""
        
        # Delete profile fact
        if self.path.startswith('/api/memory/profile/'):
            try:
                key = self.path.split('/api/memory/profile/')[1]
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                c.execute("DELETE FROM profile_facts WHERE key=?", (key,))
                conn.commit()
                deleted = c.rowcount > 0
                conn.close()
                
                if deleted:
                    response = {'status': 'success', 'message': f'Fact "{key}" slettet'}
                else:
                    response = {'status': 'error', 'message': f'Fact "{key}" ikke funnet'}
                    
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        # Delete memory
        elif self.path.startswith('/api/memory/memories/'):
            try:
                memory_id = int(self.path.split('/api/memory/memories/')[1])
                memory_manager = MemoryManager()
                conn = memory_manager._get_connection()
                c = conn.cursor()
                
                c.execute("DELETE FROM memories WHERE id=?", (memory_id,))
                conn.commit()
                deleted = c.rowcount > 0
                conn.close()
                
                if deleted:
                    response = {'status': 'success', 'message': f'Memory #{memory_id} slettet'}
                else:
                    response = {'status': 'error', 'message': f'Memory #{memory_id} ikke funnet'}
                    
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/ask-ai':
            # Send melding til AI og få respons direkte via OpenAI API
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            text = data.get('text', '').strip()
            print(f"AI-spørsmål: {text}", flush=True)
            
            if not text:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen tekst'}).encode())
                return
            
            try:
                # Import nødvendige moduler
                import os as _os
                import requests
                from dotenv import load_dotenv
                
                # Les personlighet og modell
                personality_file = '/tmp/duck_personality.txt'
                personality = 'normal'
                if _os.path.exists(personality_file):
                    with open(personality_file, 'r') as f:
                        personality = f.read().strip() or 'normal'
                
                model_file = '/tmp/duck_model.txt'
                model = 'gpt-3.5-turbo'
                if _os.path.exists(model_file):
                    with open(model_file, 'r') as f:
                        model = f.read().strip() or 'gpt-3.5-turbo'
                
                # Les API-nøkkel fra .env
                load_dotenv()
                api_key = _os.getenv('OPENAI_API_KEY')
                
                if not api_key:
                    raise Exception('OPENAI_API_KEY ikke funnet i .env')
                
                # Kall OpenAI API
                
                # Hent nåværende dato og tid
                from datetime import datetime as dt
                now = dt.now()
                date_time_info = f"Nåværende dato og tid: {now.strftime('%A %d. %B %Y, klokken %H:%M')}. "
                
                system_prompts = {
                    'normal': 'Du er en hjelpsom assistent.',
                    'entusiastic': 'Du er veldig energisk og entusiastisk!',
                    'philosophical': 'Du er en dyp tenker som reflekterer over livet.',
                    'humorous': 'Du er morsom og spøkefull.',
                    'concise': 'Du svarer kort og konsist.'
                }
                
                system_prompt = date_time_info + system_prompts.get(personality, system_prompts['normal'])
                
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': text}
                    ],
                    'max_tokens': 500,
                    'temperature': 0.7
                }
                
                api_response = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if api_response.status_code == 200:
                    result = api_response.json()
                    ai_text = result['choices'][0]['message']['content'].strip()
                    
                    response = {'success': True, 'response': ai_text}
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                else:
                    error_msg = f'OpenAI API error: {api_response.status_code}'
                    response = {'success': False, 'error': error_msg}
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                print(f"Feil i /ask-ai: {e}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/control':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            action = data.get('action')
            print(f"Handling: {action}", flush=True)
            
            try:
                if action == 'start':
                    cmd = ['sudo', 'systemctl', 'start', 'chatgpt-duck.service']
                elif action == 'stop':
                    cmd = ['sudo', 'systemctl', 'stop', 'chatgpt-duck.service']
                elif action == 'restart':
                    cmd = ['sudo', 'systemctl', 'restart', 'chatgpt-duck.service']
                else:
                    raise ValueError(f"Ugyldig handling: {action}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    response = {'success': True}
                else:
                    response = {'success': False, 'error': result.stderr}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/control':
            # Kontroller duck-servicen (start/stop/restart)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            action = data.get('action', '').strip()
            print(f"Control action: {action}", flush=True)
            
            if action not in ['start', 'stop', 'restart']:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ugyldig action'}).encode())
                return
            
            try:
                result = subprocess.run(
                    ['sudo', 'systemctl', action, 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    response = {'success': True, 'message': f'Duck {action}ed'}
                else:
                    response = {'success': False, 'error': result.stderr or 'Ukjent feil'}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/test-beak':
            # Test nebbet ved å sende en testmelding
            print("Testing beak...", flush=True)
            
            try:
                # Send en testmelding til duck
                message_file = '/tmp/duck_message.txt'
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write('Testing nebbet nå')
                
                response = {'success': True, 'message': 'Nebbet-test sendt!'}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/speak':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            text = data.get('text', '').strip()
            print(f"Speak request: {text}", flush=True)
            
            if not text:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen tekst angitt'}).encode())
                return
            
            try:
                # Sjekk om tjenesten kjører
                result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.stdout.strip() != 'active':
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Duck-servicen kjører ikke'}).encode())
                    return
                
                # Skriv melding til fil som duck-servicen sjekker
                message_file = '/tmp/duck_message.txt'
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/start-portal':
            # Start bare wifi-portal uten å bytte til hotspot
            print("Starting wifi-portal on port 80", flush=True)
            
            try:
                import os
                script_dir = os.path.dirname(os.path.abspath(__file__))
                
                # Tving WiFi-scan for å oppdatere tilgjengelige nettverk
                subprocess.run(
                    ['nmcli', 'device', 'wifi', 'rescan'],
                    capture_output=True,
                    timeout=5
                )
                
                # Sjekk om wifi-portal allerede kjører
                check_portal = subprocess.run(
                    ['pgrep', '-f', 'wifi-portal.py'],
                    capture_output=True
                )
                
                if check_portal.returncode == 0:
                    # Allerede kjører
                    response = {'success': True, 'message': 'Portal kjører allerede'}
                else:
                    # Start portal
                    portal_path = os.path.join(script_dir, 'wifi-portal.py')
                    subprocess.Popen(
                        ['python3', portal_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    response = {'success': True, 'message': 'Portal startet'}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/shutdown':
            # Shutdown Raspberry Pi
            print("Shutting down Raspberry Pi", flush=True)
            
            try:
                # Kjør shutdown kommando
                subprocess.Popen(
                    ['sudo', 'shutdown', '-h', '+0'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/reboot':
            # Reboot Raspberry Pi
            print("Rebooting Raspberry Pi", flush=True)
            
            try:
                # Kjør reboot kommando
                subprocess.Popen(
                    ['sudo', 'reboot'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-personality':
            # Endre personlighet
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            personality = data.get('personality')
            print(f"Endrer personlighet til: {personality}", flush=True)
            
            try:
                # Skriv personlighet til fil
                personality_file = '/tmp/duck_personality.txt'
                with open(personality_file, 'w', encoding='utf-8') as f:
                    f.write(personality)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-voice':
            # Endre TTS-stemme
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            voice = data.get('voice')
            print(f"Endrer TTS-stemme til: {voice}", flush=True)
            
            try:
                # Skriv stemme til fil
                voice_file = '/tmp/duck_voice.txt'
                with open(voice_file, 'w', encoding='utf-8') as f:
                    f.write(voice)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-beak':
            # Endre nebbet-status (on/off)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            beak = data.get('beak')
            print(f"Endrer nebbet til: {beak}", flush=True)
            
            try:
                # Skriv nebbet-status til fil
                beak_file = '/tmp/duck_beak.txt'
                with open(beak_file, 'w', encoding='utf-8') as f:
                    f.write(beak)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-speed':
            # Endre talehastighet (0-100, hvor 50 er normal)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            speed = int(data.get('speed', 50))
            # Clamp til 0-100
            speed = max(0, min(100, speed))
            
            print(f"Endrer talehastighet til: {speed}", flush=True)
            
            try:
                # Skriv hastighet til fil
                speed_file = '/tmp/duck_speed.txt'
                with open(speed_file, 'w', encoding='utf-8') as f:
                    f.write(str(speed))
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-volume':
            # Endre volum (0-100)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            volume = int(data.get('volume', 50))
            # Clamp til 0-100
            volume = max(0, min(100, volume))
            
            print(f"Endrer volum til: {volume}", flush=True)
            
            try:
                # Skriv volum til fil
                volume_file = '/tmp/duck_volume.txt'
                with open(volume_file, 'w', encoding='utf-8') as f:
                    f.write(str(volume))
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/set-fan-mode':
            # Endre viftemodus (auto/on/off)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            mode = data.get('mode', 'auto').lower()
            if mode not in ['auto', 'on', 'off']:
                mode = 'auto'
            
            print(f"Endrer viftemodus til: {mode}", flush=True)
            
            try:
                # Skriv modus til fil
                mode_file = '/tmp/duck_fan.txt'
                with open(mode_file, 'w', encoding='utf-8') as f:
                    f.write(mode)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/start-conversation':
            # Trigger en samtale uten wake word
            print("Starting conversation without wake word", flush=True)
            
            try:
                # Sjekk om servicen kjører
                result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.stdout.strip() != 'active':
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Duck-servicen kjører ikke'}).encode())
                    return
                
                # Skriv spesiell trigger til fil som duck-servicen sjekker
                message_file = '/tmp/duck_message.txt'
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write('__START_CONVERSATION__')
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-model':
            # Endre AI-modell
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            model = data.get('model')
            print(f"Endrer AI-modell til: {model}", flush=True)
            
            try:
                # Skriv modell til fil
                model_file = '/tmp/duck_model.txt'
                with open(model_file, 'w', encoding='utf-8') as f:
                    f.write(model)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/play-song':
            # Spill av en sang
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            song_path = data.get('song_path', '').strip()
            print(f"Sang-forespørsel: {song_path}", flush=True)
            
            if not song_path:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen sang valgt'}).encode())
                return
            
            try:
                # Sjekk om servicen kjører
                result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.stdout.strip() != 'active':
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Duck-servicen kjører ikke'}).encode())
                    return
                
                # Skriv sangforespørsel til fil
                song_request_file = '/tmp/duck_song_request.txt'
                with open(song_request_file, 'w', encoding='utf-8') as f:
                    f.write(song_path)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/stop-song':
            # Stopp sang
            print("Stopp sang-forespørsel", flush=True)
            
            try:
                # Skriv stopp-forespørsel til fil
                song_stop_file = '/tmp/duck_song_stop.txt'
                with open(song_stop_file, 'w', encoding='utf-8') as f:
                    f.write('stop')
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/api/settings/memory':
            # Oppdater memory settings
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                
                mm = MemoryManager()
                conn = mm._get_connection()
                c = conn.cursor()
                
                updated = {}
                
                # Embedding search limit
                if 'embedding_search_limit' in data:
                    val = int(data['embedding_search_limit'])
                    if not (10 <= val <= 100):
                        raise ValueError("embedding_search_limit må være mellom 10 og 100")
                    c.execute("""
                        INSERT OR REPLACE INTO profile_facts 
                        (key, value, topic, confidence, frequency, source, last_updated, metadata)
                        VALUES (?, ?, 'system', 1.0, 10, 'user', datetime('now'), ?)
                    """, ('embedding_search_limit', str(val), json.dumps({'source': 'control_panel'})))
                    updated['embedding_search_limit'] = val
                
                # Memory limit  
                if 'memory_limit' in data:
                    val = int(data['memory_limit'])
                    if not (1 <= val <= 20):
                        raise ValueError("memory_limit må være mellom 1 og 20")
                    c.execute("""
                        INSERT OR REPLACE INTO profile_facts 
                        (key, value, topic, confidence, frequency, source, last_updated, metadata)
                        VALUES (?, ?, 'system', 1.0, 10, 'user', datetime('now'), ?)
                    """, ('memory_limit', str(val), json.dumps({'source': 'control_panel'})))
                    updated['memory_limit'] = val
                
                # Memory threshold
                if 'memory_threshold' in data:
                    val = float(data['memory_threshold'])
                    if not (0.2 <= val <= 0.8):
                        raise ValueError("memory_threshold må være mellom 0.2 og 0.8")
                    c.execute("""
                        INSERT OR REPLACE INTO profile_facts 
                        (key, value, topic, confidence, frequency, source, last_updated, metadata)
                        VALUES (?, ?, 'system', 1.0, 10, 'user', datetime('now'), ?)
                    """, ('memory_threshold', str(val), json.dumps({'source': 'control_panel'})))
                    updated['memory_threshold'] = val
                
                conn.commit()
                conn.close()
                
                response = {'success': True, **updated}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/api/settings/max-context-facts':
            # Oppdater max_context_facts setting
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                
                max_facts = int(data.get('max_context_facts', 100))
                
                # Valider range
                if not (1 <= max_facts <= 200):
                    raise ValueError("max_context_facts må være mellom 1 og 200")
                
                mm = MemoryManager()
                conn = mm._get_connection()
                c = conn.cursor()
                
                # Insert eller update
                c.execute("""
                    INSERT OR REPLACE INTO profile_facts 
                    (key, value, topic, confidence, frequency, source, last_updated, metadata)
                    VALUES (?, ?, 'system', 1.0, 10, 'user', datetime('now'), ?)
                """, ('max_context_facts', str(max_facts), json.dumps({'source': 'control_panel'})))
                
                conn.commit()
                conn.close()
                
                response = {'success': True, 'max_context_facts': max_facts}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/api/users/switch':
            # Bytt bruker
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            username = data.get('username', '').strip()
            
            if not username:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen bruker valgt'}).encode())
                return
            
            try:
                user_manager = UserManager()
                
                # Hent bruker fra database
                found_user = user_manager.find_user_by_name(username)
                
                if not found_user:
                    # Ikke funnet i profile_facts - sjekk i users tabell direkte
                    conn = user_manager._get_connection()
                    c = conn.cursor()
                    c.execute("SELECT display_name, relation_to_primary FROM users WHERE username = ?", (username,))
                    row = c.fetchone()
                    conn.close()
                    
                    if row:
                        found_user = {
                            'username': username,
                            'display_name': row['display_name'],
                            'relation': row['relation_to_primary']
                        }
                    else:
                        raise Exception(f"Bruker '{username}' ikke funnet")
                
                # Bytt bruker
                user_manager.switch_user(
                    username=found_user['username'],
                    display_name=found_user['display_name'],
                    relation=found_user['relation']
                )
                
                response = {
                    'success': True,
                    'username': found_user['username'],
                    'display_name': found_user['display_name']
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}", flush=True)

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 3000), DuckControlHandler)
    print("🦆 Duck Control Panel kjører på http://0.0.0.0:3000")
    print("   Tilgjengelig på: http://oduckberry:3000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutter...")
        server.shutdown()
