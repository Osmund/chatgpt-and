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
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))

from duck_services import get_services
from duck_api_handlers import DuckAPIHandlers

# Template directory
TEMPLATE_DIR = Path(__file__).parent / 'templates'

# Initialize services once at startup
services = get_services()
api_handlers = DuckAPIHandlers(services)


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
    def send_json_response(self, data, status_code=200):
        """Helper method to send JSON responses"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
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
        
        elif self.path == '/upload-image':
            # Bilde-upload side
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            html_content = load_template('upload.html')
            self.wfile.write(html_content.encode())
        
        elif self.path == '/status':
            response = api_handlers.handle_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/duck-status':
            response = api_handlers.handle_duck_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/ha-status':
            response = api_handlers.handle_ha_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/duck_location':
            response = api_handlers.handle_duck_location()
            self.send_json_response(response, 200)
        
        elif self.path == '/boredom-status':
            response = api_handlers.handle_boredom_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/vision-status':
            response = api_handlers.handle_vision_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/hunger-status':
            # Hent sultbarometer fra database
            try:
                import sqlite3
                import sys
                sys.path.insert(0, str(Path(__file__).parent / 'src'))
                
                hunger_manager = services.get_hunger_manager()
                status = hunger_manager.get_status()
                
                level = status.get('level', 0)
                
                # Bestem emoji og farge basert på nivå
                if level < 3:
                    emoji = "😊"
                    color = "#4ade80"  # grønn
                    status_text = "Mett"
                elif level < 5:
                    emoji = "🙂"
                    color = "#a3e635"  # lime
                    status_text = "OK"
                elif level < 7:
                    emoji = "😐"
                    color = "#fbbf24"  # gul
                    status_text = "Litt sulten"
                elif level < 9:
                    emoji = "😟"
                    color = "#fb923c"  # oransje
                    status_text = "Sulten"
                else:
                    emoji = "😩"
                    color = "#ef4444"  # rød
                    status_text = "VELDIG SULTEN!"
                
                response = {
                    'level': level,
                    'emoji': emoji,
                    'color': color,
                    'status': status_text,
                    'mood': status.get('mood', 'content'),
                    'meals_today': status.get('meals_today', 0),
                    'next_meal_time': status.get('next_meal_time', '12:00')
                }
            except Exception as e:
                response = {'level': 0, 'emoji': '😊', 'color': '#4ade80', 'status': 'Mett', 'error': str(e)}
            
            self.send_json_response(response, 200)
        
        elif self.path == '/logs':
            response = api_handlers.handle_logs(lines=50)
            self.send_json_response(response, 200)
        
        elif self.path == '/current-model':
            response = api_handlers.handle_current_model()
            self.send_json_response(response, 200)
        
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
            
            self.send_json_response(response, 200)
        
        elif self.path == '/current-personality':
            response = api_handlers.handle_current_personality()
            self.send_json_response(response, 200)
        
        elif self.path == '/current-voice':
            response = api_handlers.handle_current_voice()
            self.send_json_response(response, 200)
        
        elif self.path == '/current-beak':
            response = api_handlers.handle_current_beak()
            self.send_json_response(response, 200)
        
        elif self.path == '/current-speed':
            response = api_handlers.handle_current_speed()
            self.send_json_response(response, 200)
        
        elif self.path == '/current-volume':
            response = api_handlers.handle_current_volume()
            self.send_json_response(response, 200)
        
        elif self.path == '/wake-words':
            response = api_handlers.handle_wake_words()
            self.send_json_response(response, 200)
        
        elif self.path == '/fan-status':
            response = api_handlers.handle_fan_status()
            self.send_json_response(response, 200)
            
            self.send_json_response(response, 200)
        
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
            
            self.send_json_response(response, 200)
        
        elif self.path == '/sleep_status':
            # Hent sleep mode status
            try:
                from src.duck_sleep import get_sleep_status
                status = get_sleep_status()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(status).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = {'enabled': False, 'error': str(e)}
                self.wfile.write(json.dumps(error_msg).encode())
        
        elif self.path == '/sms_history':
            # Hent SMS-historikk OG duck messages kombinert
            try:
                import sqlite3
                db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("""
                    SELECT 
                        h.id,
                        h.direction,
                        h.message,
                        h.timestamp,
                        h.status,
                        c.name,
                        c.phone,
                        'sms' as message_type
                    FROM sms_history h
                    LEFT JOIN sms_contacts c ON h.contact_id = c.id
                    
                    UNION ALL
                    
                    SELECT
                        d.id,
                        d.direction,
                        d.message,
                        d.timestamp,
                        'delivered' as status,
                        d.from_duck || ' → ' || d.to_duck as name,
                        NULL as phone,
                        'duck' as message_type
                    FROM duck_messages d
                    
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)
                
                rows = c.fetchall()
                conn.close()
                
                sms_list = []
                for row in rows:
                    sms_list.append({
                        'id': row['id'],
                        'direction': row['direction'],
                        'message': row['message'],
                        'timestamp': row['timestamp'],
                        'status': row['status'],
                        'contact_name': row['name'] if row['name'] else 'Ukjent',
                        'phone_number': row['phone'] if row['phone'] else None,
                        'message_type': row['message_type']  # 'sms' eller 'duck'
                    })
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(sms_list).encode())
            except Exception as e:
                print(f"⚠️ Error fetching SMS history: {e}", flush=True)
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = {'error': str(e)}
                self.wfile.write(json.dumps(error_msg).encode())
        
        elif self.path == '/sms_contacts':
            # Hent alle SMS-kontakter
            try:
                import sqlite3
                db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("""
                    SELECT id, name, phone, relation, priority, enabled, 
                           max_daily_messages, preferred_hours_start, preferred_hours_end
                    FROM sms_contacts 
                    ORDER BY name ASC
                """)
                
                rows = c.fetchall()
                conn.close()
                
                contacts = []
                for row in rows:
                    contacts.append({
                        'id': row[0],
                        'name': row[1],
                        'phone': row[2],
                        'relation': row[3],
                        'priority': row[4],
                        'enabled': bool(row[5]),
                        'max_daily_messages': row[6],
                        'preferred_hours_start': row[7],
                        'preferred_hours_end': row[8]
                    })
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(contacts).encode())
            except Exception as e:
                print(f"⚠️ Error fetching contacts: {e}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = {'error': str(e)}
                self.wfile.write(json.dumps(error_msg).encode())
        
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
            
            self.send_json_response(response, 200)
        
        # ==================== MEMORY API ====================
        elif self.path == '/api/memory/stats':
            response = api_handlers.handle_memory_stats()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/profile':
            response = api_handlers.handle_memory_profile()
            self.send_json_response(response, 200)
        
        elif self.path.startswith('/api/memory/memories'):
            # Get memories with optional search
            try:
                memory_manager = services.get_memory_manager()
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
            
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/topics':
            response = api_handlers.handle_memory_topics()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/conversations':
            response = api_handlers.handle_memory_conversations()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/embedding-status':
            response = api_handlers.handle_memory_embedding_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/worker-status':
            response = api_handlers.handle_memory_worker_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/recent-updates':
            response = api_handlers.handle_memory_recent_updates()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/memory/quick-facts':
            response = api_handlers.handle_memory_quick_facts()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/settings/max-context-facts':
            response = api_handlers.handle_settings_max_context_facts()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/settings/memory':
            response = api_handlers.handle_settings_memory()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/users/current':
            response = api_handlers.handle_users_current()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/users/list':
            response = api_handlers.handle_users_list()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/personality':
            # Hent personlighetsprofil
            try:
                import sqlite3
                conn = sqlite3.connect('/home/admog/Code/chatgpt-and/duck_memory.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                c.execute("SELECT * FROM personality_profile WHERE id = 1")
                row = c.fetchone()
                conn.close()
                
                if row:
                    response = {
                        'humor_level': row['humor_level'],
                        'verbosity_level': row['verbosity_level'],
                        'formality_level': row['formality_level'],
                        'enthusiasm_level': row['enthusiasm_level'],
                        'technical_depth': row['technical_depth'],
                        'empathy_level': row['empathy_level'] if 'empathy_level' in row.keys() else 5.0,
                        'directness_level': row['directness_level'] if 'directness_level' in row.keys() else 5.0,
                        'creativity_level': row['creativity_level'] if 'creativity_level' in row.keys() else 5.0,
                        'boundary_level': row['boundary_level'] if 'boundary_level' in row.keys() else 5.0,
                        'proactivity_level': row['proactivity_level'] if 'proactivity_level' in row.keys() else 5.0,
                        'ask_followup_questions': bool(row['ask_followup_questions']),
                        'use_emojis': bool(row['use_emojis']),
                        'confidence_score': row['confidence_score'],
                        'conversations_analyzed': row['conversations_analyzed'],
                        'last_analyzed': row['last_analyzed']
                    }
                else:
                    response = {'error': 'Ingen profil funnet'}
            except Exception as e:
                response = {'error': str(e)}
            
            self.send_json_response(response, 200)
        
        elif self.path == '/api/backup':
            response = api_handlers.handle_backup_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/wake-word/sensitivity':
            response = api_handlers.handle_get_sensitivity()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/hunger/feed':
            # POST endpoint - handled in do_POST
            self.send_response(405)
            self.end_headers()
        
        elif self.path == '/api/printer/status':
            response = api_handlers.handle_printer_status()
            self.send_json_response(response, 200)
        
        elif self.path == '/api/system/stats':
            response = api_handlers.handle_system_stats()
            self.send_json_response(response, 200)
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_PUT(self):
        """Handle PUT requests for updating resources"""
        
        # Update SMS contact
        if self.path.startswith('/sms_contacts/'):
            try:
                contact_id = int(self.path.split('/sms_contacts/')[1])
                
                content_length = int(self.headers['Content-Length'])
                put_data = self.rfile.read(content_length)
                data = json.loads(put_data.decode())
                
                import sqlite3
                db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("""
                    UPDATE sms_contacts 
                    SET name=?, phone=?, relation=?, priority=?, enabled=?, 
                        max_daily_messages=?, preferred_hours_start=?, preferred_hours_end=?
                    WHERE id=?
                """, (
                    data.get('name', ''),
                    data.get('phone', ''),
                    data.get('relation', 'venn'),
                    data.get('priority', 5),
                    1 if data.get('enabled', True) else 0,
                    data.get('max_daily_messages', 3),
                    data.get('preferred_hours_start', 8),
                    data.get('preferred_hours_end', 22),
                    contact_id
                ))
                conn.commit()
                updated = c.rowcount > 0
                conn.close()
                
                if updated:
                    response = {'success': True, 'message': f'Kontakt #{contact_id} oppdatert'}
                else:
                    response = {'success': False, 'message': f'Kontakt #{contact_id} ikke funnet'}
                    
            except Exception as e:
                print(f"⚠️ Error updating contact: {e}", flush=True)
                response = {'success': False, 'error': str(e)}
            
            self.send_json_response(response, 200)
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_DELETE(self):
        """Handle DELETE requests for memory management"""
        
        # Delete profile fact
        if self.path.startswith('/api/memory/profile/'):
            try:
                key = self.path.split('/api/memory/profile/')[1]
                memory_manager = services.get_memory_manager()
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
            
            self.send_json_response(response, 200)
        
        # Delete memory
        elif self.path.startswith('/api/memory/memories/'):
            try:
                memory_id = int(self.path.split('/api/memory/memories/')[1])
                memory_manager = services.get_memory_manager()
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
            
            self.send_json_response(response, 200)
        
        # Delete SMS contact
        elif self.path.startswith('/sms_contacts/'):
            try:
                contact_id = int(self.path.split('/sms_contacts/')[1])
                
                import sqlite3
                db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("DELETE FROM sms_contacts WHERE id=?", (contact_id,))
                conn.commit()
                deleted = c.rowcount > 0
                conn.close()
                
                if deleted:
                    response = {'success': True, 'message': f'Kontakt #{contact_id} slettet'}
                else:
                    response = {'success': False, 'message': f'Kontakt #{contact_id} ikke funnet'}
                    
            except Exception as e:
                print(f"⚠️ Error deleting contact: {e}", flush=True)
                response = {'success': False, 'error': str(e)}
            
            self.send_json_response(response, 200)
        
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
                    self.send_json_response(response, 200)
                else:
                    error_msg = f'OpenAI API error: {api_response.status_code}'
                    response = {'success': False, 'error': error_msg}
                    self.send_json_response(response, 500)
                
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
                
                self.send_json_response(response, 200)
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
                
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                
                self.send_json_response(response, 200)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/shutdown':
            # Graceful shutdown of Anda before shutting down Pi
            print("🛑 Starting graceful shutdown of Anda and Raspberry Pi", flush=True)
            
            try:
                # Run graceful shutdown script first (with longer timeout for backup)
                shutdown_script = '/home/admog/Code/chatgpt-and/scripts/graceful-shutdown.sh'
                if os.path.exists(shutdown_script):
                    print("  Running graceful shutdown script...", flush=True)
                    subprocess.run(
                        ['bash', shutdown_script],
                        timeout=30  # Longer timeout to allow backup to complete
                    )
                
                # Then shutdown the system (use 'now' instead of '+0')
                print("  Initiating system shutdown...", flush=True)
                subprocess.Popen(
                    ['sudo', 'shutdown', '-h', 'now'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                response = {'success': True, 'message': 'Graceful shutdown initiated'}
                self.send_json_response(response, 200)
            except subprocess.TimeoutExpired:
                # If graceful shutdown times out, still try to shut down
                print("⚠️  Graceful shutdown timed out, forcing shutdown...", flush=True)
                subprocess.Popen(
                    ['sudo', 'shutdown', '-h', 'now'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                response = {'success': True, 'message': 'Shutdown initiated (graceful timeout)'}
                self.send_json_response(response, 200)
            except Exception as e:
                print(f"❌ Shutdown error: {e}", flush=True)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
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
                self.send_json_response(response, 200)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/sleep/enable':
            # Aktiver sleep mode
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            duration_minutes = data.get('duration_minutes', 60)
            print(f"Sleep mode enable: {duration_minutes} minutter", flush=True)
            
            try:
                from src.duck_sleep import enable_sleep
                result = enable_sleep(duration_minutes)
                
                if result.get('success'):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/sleep/disable':
            # Deaktiver sleep mode
            print("Sleep mode disable", flush=True)
            
            try:
                from src.duck_sleep import disable_sleep
                result = disable_sleep()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
                response = {'success': True}
                self.send_json_response(response, 200)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/sms_contacts':
            # Legg til ny SMS-kontakt
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                
                import sqlite3
                db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO sms_contacts 
                    (name, phone, relation, priority, enabled, max_daily_messages, preferred_hours_start, preferred_hours_end)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('name', ''),
                    data.get('phone', ''),
                    data.get('relation', 'venn'),
                    data.get('priority', 5),
                    1 if data.get('enabled', True) else 0,
                    data.get('max_daily_messages', 3),
                    data.get('preferred_hours_start', 8),
                    data.get('preferred_hours_end', 22)
                ))
                conn.commit()
                new_id = c.lastrowid
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'id': new_id}).encode())
            except Exception as e:
                print(f"⚠️ Error adding contact: {e}", flush=True)
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
                
                mm = services.get_memory_manager()
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
                self.send_json_response(response, 200)
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
                
                mm = services.get_memory_manager()
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
                self.send_json_response(response, 200)
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
                user_manager = services.get_user_manager()
                
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
                
                self.send_json_response(response, 200)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/api/personality/update':
            # Oppdater personlighetsprofil
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                
                import sqlite3
                conn = sqlite3.connect('/home/admog/Code/chatgpt-and/duck_memory.db')
                c = conn.cursor()
                
                # Oppdater alle dimensjoner
                c.execute("""
                    UPDATE personality_profile SET
                        humor_level = ?,
                        verbosity_level = ?,
                        formality_level = ?,
                        enthusiasm_level = ?,
                        technical_depth = ?,
                        empathy_level = ?,
                        directness_level = ?,
                        creativity_level = ?,
                        boundary_level = ?,
                        proactivity_level = ?
                    WHERE id = 1
                """, (
                    float(data.get('humor_level', 5.0)),
                    float(data.get('verbosity_level', 5.0)),
                    float(data.get('formality_level', 3.0)),
                    float(data.get('enthusiasm_level', 5.0)),
                    float(data.get('technical_depth', 5.0)),
                    float(data.get('empathy_level', 5.0)),
                    float(data.get('directness_level', 5.0)),
                    float(data.get('creativity_level', 5.0)),
                    float(data.get('boundary_level', 5.0)),
                    float(data.get('proactivity_level', 5.0))
                ))
                
                conn.commit()
                conn.close()
                
                # Restart service for å laste ny profil
                subprocess.run(
                    ['sudo', 'systemctl', 'restart', 'chatgpt-duck.service'],
                    capture_output=True, timeout=10
                )
                
                response = {'success': True, 'message': 'Personlighet oppdatert og service restartet'}
                self.send_json_response(response, 200)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/webhook/sms':
            # SMS webhook from relay server
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                from_number = data.get('from')
                message = data.get('message')
                
                print(f"📨 Incoming SMS from {from_number}: {message[:50]}...", flush=True)
                
                # Import SMS manager and handle
                try:
                    import sys
                    sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
                    from duck_sms import SMSManager
                    
                    sms_manager = SMSManager()
                    sms_manager.handle_incoming_sms(from_number, message)
                    print(f"✅ SMS processed successfully", flush=True)
                except Exception as sms_error:
                    print(f"⚠️ SMS handling error: {sms_error}", flush=True)
                
                response = {'status': 'received', 'from': from_number}
                self.send_json_response(response, 200)
            except Exception as e:
                print(f"❌ SMS webhook error: {e}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())
        
        elif self.path == '/upload-image-submit':
            # Handle image upload using dedicated handler
            try:
                from image_upload_handler import handle_image_upload
                
                # Read body
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                content_type = self.headers['Content-Type']
                
                # Process upload
                result = handle_image_upload(body, content_type, services)
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
                
            except Exception as e:
                print(f"❌ Image upload error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
                
            except Exception as e:
                print(f"❌ Image upload error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/api/backup/start':
            response = api_handlers.handle_backup_start()
            status_code = 200 if response.get('status') == 'success' else 500
            self.send_json_response(response, status_code)
        
        elif self.path == '/api/wake-word/sensitivity':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                sensitivity = float(data.get('sensitivity', 0.9))
                response = api_handlers.handle_set_sensitivity(sensitivity)
                status_code = 200 if response.get('status') == 'success' else 400
                self.send_json_response(response, status_code)
            except Exception as e:
                self.send_json_response({'status': 'error', 'message': str(e)}, 400)
        
        elif self.path == '/api/hunger/feed':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                food_type = data.get('food_type', 'cookie')
                response = api_handlers.handle_feed(food_type)
                self.send_json_response(response, 200)
            except Exception as e:
                self.send_json_response({'status': 'error', 'message': str(e)}, 400)
        
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
