#!/usr/bin/env python3
"""
Enkel web-portal for WiFi-konfigurasjon av ChatGPT Duck
Kjør på port 80 når hotspot er aktivert
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import urllib.parse
import json
import time
import os

# Cache for network list (unngå gjentatte scans)
network_cache = {'data': {}, 'timestamp': 0}
CACHE_DURATION = 5  # sekunder (redusert for bedre oppdatering)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChatGPT Duck WiFi Setup</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: #f0f0f0;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #ff9800;
            text-align: center;
        }
        .network {
            padding: 15px;
            margin: 10px 0;
            background: #f9f9f9;
            border-radius: 5px;
            cursor: pointer;
            border: 2px solid transparent;
        }
        .network:hover {
            border-color: #ff9800;
        }
        .signal {
            float: right;
            color: #4CAF50;
        }
        input[type="password"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        button {
            background: #ff9800;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        button:hover {
            background: #e68900;
        }
        .status {
            margin: 20px 0;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
        .success {
            background: #d4edda;
            color: #155724;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🦆 ChatGPT Duck</h1>
        <h2>WiFi Setup</h2>
        
        {status}
        
        <p style="text-align: center; color: #666; font-size: 0.9em;">
            🔒 = Sikret nettverk | ⭐ = Lagret nettverk
        </p>
        
        <div id="networks">
            {networks}
        </div>
        
        <div id="connect-form" style="display:none; margin-top: 20px;">
            <h3>Koble til: <span id="selected-ssid"></span></h3>
            <input type="password" id="password" placeholder="WiFi-passord">
            <button onclick="connect()">Koble til</button>
            <button onclick="cancelConnect()" style="background: #666; margin-top: 10px;">Avbryt</button>
        </div>
    </div>
    
    <script>
        let selectedSSID = '';
        
        function selectNetwork(ssid) {
            selectedSSID = ssid;
            document.getElementById('selected-ssid').textContent = ssid;
            document.getElementById('connect-form').style.display = 'block';
            document.getElementById('password').focus();
        }
        
        function cancelConnect() {
            document.getElementById('connect-form').style.display = 'none';
            document.getElementById('password').value = '';
        }
        
        function connect() {
            const password = document.getElementById('password').value;
            if (!password) {
                alert('Vennligst skriv inn passord');
                return;
            }
            
            fetch('/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ssid: selectedSSID, password: password})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Tilkobling vellykket! ChatGPT Duck vil nå koble til nettverket.');
                    setTimeout(() => location.reload(), 2000);
                } else {
                    alert('Feil: ' + data.error);
                }
            });
        }
    </script>
</body>
</html>
"""

class WiFiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            # Hent tilgjengelige nettverk
            try:
                # Hent liste over lagrede connections
                saved_connections = set()
                conn_result = subprocess.run(
                    ['sudo', 'nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                    capture_output=True, text=True, timeout=5
                )
                for line in conn_result.stdout.split('\n'):
                    if line and ':wifi' in line.lower():
                        conn_name = line.split(':')[0]
                        if not conn_name.startswith('temp-'):
                            saved_connections.add(conn_name)
                
                # Tving rescan først
                subprocess.run(
                    ['sudo', 'nmcli', 'device', 'wifi', 'rescan'],
                    capture_output=True, timeout=3
                )
                time.sleep(1)  # Gi litt tid til scan
                
                result = subprocess.run(
                    ['sudo', 'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list'],
                    capture_output=True, text=True, timeout=15
                )
                networks_html = ""
                
                # Bygg også cache for sikkerhet-info
                current_time = time.time()
                network_cache['data'] = {}
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            ssid = parts[0]
                            signal = parts[1] if len(parts) > 1 else '?'
                            security = parts[2] if len(parts) > 2 else ''
                            if ssid:  # Ignorer tomme SSID
                                # Lagre sikkerhet i cache
                                network_cache['data'][ssid] = bool(security.strip())
                                
                                lock = '🔒' if security else ''
                                saved = '⭐' if ssid in saved_connections else ''
                                networks_html += f'''
                                <div class="network" onclick="selectNetwork('{ssid}')">
                                    <strong>{lock} {ssid} {saved}</strong>
                                    <span class="signal">{signal}%</span>
                                </div>
                                '''
                
                network_cache['timestamp'] = current_time
                
                status = ''
                # Sjekk current connection
                try:
                    conn_result = subprocess.run(
                        ['sudo', 'nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show', '--active'],
                        capture_output=True, text=True, timeout=5
                    )
                    if 'wifi' in conn_result.stdout.lower():
                        status = '<div class="status success">✓ Koblet til WiFi</div>'
                except:
                    pass
                
                # Bruk enkel replace i stedet for str.format for å unngå at
                # JavaScript/CSS-braces blir tolket som format-plassholdere.
                html = HTML_TEMPLATE.replace('{networks}', networks_html).replace('{status}', status)
                self.wfile.write(html.encode())
            except Exception as e:
                self.wfile.write(f"<h1>Feil: {e}</h1>".encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/connect':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            ssid = data.get('ssid')
            password = data.get('password')
            
            print(f"Forsøk på tilkobling til: {ssid}", flush=True)
            
            try:
                # Bruk cache hvis tilgjengelig og ferskt nok
                current_time = time.time()
                has_security = False
                
                if (current_time - network_cache['timestamp'] < CACHE_DURATION and 
                    ssid in network_cache['data']):
                    has_security = network_cache['data'][ssid]
                    print(f"Bruker cache: sikkerhet={has_security}", flush=True)
                else:
                    print("Cache mangler, hopper over sikkerhet-sjekk", flush=True)
                
                # Bygg nmcli-kommando
                if password:
                    # Sjekk om det allerede finnes en connection for dette nettverket
                    check_existing = subprocess.run(
                        ['sudo', 'nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    existing_conn = None
                    for line in check_existing.stdout.split('\n'):
                        if line:
                            parts = line.split(':')
                            conn_name = parts[0]
                            # Sjekk om connection-navnet matcher SSID (ignorer temp- connections)
                            if conn_name == ssid and not conn_name.startswith('temp-'):
                                existing_conn = conn_name
                                break
                    
                    if existing_conn:
                        print(f"Bruker eksisterende connection: {existing_conn}", flush=True)
                        # Oppdater passord og autoconnect-innstillinger
                        subprocess.run([
                            'sudo', 'nmcli', 'connection', 'modify', existing_conn,
                            'wifi-sec.psk', password,
                            'connection.autoconnect', 'yes',
                            'connection.autoconnect-priority', '10'
                        ], capture_output=True, timeout=5)
                        
                        cmd = ['sudo', 'nmcli', 'connection', 'up', existing_conn]
                    else:
                        # Opprett ny connection med SSID som navn (ikke temp-)
                        print(f"Oppretter ny connection: {ssid}", flush=True)
                        
                        # Opprett ny connection med WPA-PSK og autoconnect
                        add_result = subprocess.run([
                            'sudo', 'nmcli', 'connection', 'add',
                            'type', 'wifi',
                            'con-name', ssid,
                            'ssid', ssid,
                            'wifi-sec.key-mgmt', 'wpa-psk',
                            'wifi-sec.psk', password,
                            'connection.autoconnect', 'yes',
                            'connection.autoconnect-priority', '10'
                        ], capture_output=True, text=True, timeout=10)
                        
                        if add_result.returncode != 0:
                            print(f"Feil ved opprettelse: {add_result.stderr}", flush=True)
                            response = {'success': False, 'error': f"Kunne ikke opprette connection: {add_result.stderr}"}
                            self.send_response(500)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps(response).encode())
                            return
                        
                        # Aktiver connection
                        cmd = ['sudo', 'nmcli', 'connection', 'up', ssid]
                    
                    print(f"Kommando: {' '.join(cmd)}", flush=True)
                else:
                    # Åpent nettverk
                    cmd = ['sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid]
                    print(f"Kommando: sudo nmcli dev wifi connect '{ssid}'", flush=True)
                
                # Prøv å koble til
                print("Kobler til...", flush=True)
                
                # Start LED blinking for å vise at noe skjer (lagre prosess for å stoppe den senere)
                led_blink_process = subprocess.Popen([
                    'sudo', '-u', 'admog',
                    '/home/admog/Code/chatgpt-and/.venv/bin/python3', '-c',
                    'from rgb_duck import blink_yellow_purple; blink_yellow_purple(); import time; time.sleep(60)'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Voice announcement: Prøver å koble til
                with open('/tmp/duck_hotspot_announcement.txt', 'w', encoding='utf-8') as f:
                    f.write(f"Jeg prøver å koble til {ssid} nå...")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                finally:
                    # Stopp LED-blinking prosess
                    try:
                        led_blink_process.terminate()
                        led_blink_process.wait(timeout=1)
                    except:
                        pass
                
                print(f"Return code: {result.returncode}", flush=True)
                print(f"Stdout: {result.stdout}", flush=True)
                print(f"Stderr: {result.stderr}", flush=True)
                
                if result.returncode == 0:
                    print("Tilkobling vellykket!", flush=True)
                    
                    # Sett LED til grønn
                    subprocess.run([
                        'sudo', '-u', 'admog',
                        '/home/admog/Code/chatgpt-and/.venv/bin/python3', '-c',
                        'from rgb_duck import set_green; set_green()'
                    ], capture_output=True, timeout=2)
                    
                    # Voice announcement: Vellykket
                    with open('/tmp/duck_hotspot_announcement.txt', 'w', encoding='utf-8') as f:
                        f.write(f"Supert! Jeg er nå koblet til {ssid}. Hotspot stoppes og jeg starter opp igjen.")
                    
                    # Verifiser at vi har internett (ping test)
                    time.sleep(2)  # Vent litt for at connection skal stabilisere seg
                    ping_result = subprocess.run(
                        ['ping', '-c', '1', '-W', '3', '8.8.8.8'],
                        capture_output=True, timeout=5
                    )
                    
                    if ping_result.returncode != 0:
                        print("ADVARSEL: Tilkoblet WiFi men ingen internett-tilgang", flush=True)
                    
                    # Stopp monitor først (den vil prøve å stoppe hotspot om den ser WiFi)
                    if os.path.exists('/tmp/hotspot_monitor.pid'):
                        try:
                            with open('/tmp/hotspot_monitor.pid', 'r') as f:
                                monitor_pid = int(f.read().strip())
                            subprocess.run(['kill', str(monitor_pid)], capture_output=True, timeout=2)
                            os.remove('/tmp/hotspot_monitor.pid')
                            print(f"Stoppet monitor (PID: {monitor_pid})", flush=True)
                        except Exception as e:
                            print(f"Kunne ikke stoppe monitor: {e}", flush=True)
                    
                    # Stopp hotspot eksplisitt
                    print("Stopper hotspot...", flush=True)
                    subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'down', 'Hotspot'],
                        capture_output=True, timeout=5
                    )
                    
                    # Start Duck service (monitor er stoppet, så vi må gjøre det)
                    print("Starter Duck service...", flush=True)
                    subprocess.run(['sudo', 'systemctl', 'restart', 'chatgpt-duck.service'],
                                 capture_output=True, timeout=10)
                    
                    response = {'success': True, 'message': 'WiFi tilkoblet! Hotspot stoppes og Duck starter...'}
                    
                    # Send response først
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                    
                    # Vent litt så response kommer frem, så avslutt portal
                    time.sleep(2)
                    print("Portal avslutter (WiFi tilkoblet)", flush=True)
                    os._exit(0)  # Avslutt prosessen
                    
                else:
                    # Blink LED raskt for feil, deretter tilbake til gul
                    try:
                        # Kjør et lite Python-script for feil-feedback
                        subprocess.run([
                            'sudo', '-u', 'admog',
                            '/home/admog/Code/chatgpt-and/.venv/bin/python3', '-c',
                            'from rgb_duck import blink_yellow, set_yellow; import time; blink_yellow(); time.sleep(3); set_yellow()'
                        ], capture_output=True, timeout=5)
                    except:
                        pass  # LED-feil skal ikke stoppe programmet
                    
                    # Voice announcement: Feilet
                    error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                    with open('/tmp/duck_hotspot_announcement.txt', 'w', encoding='utf-8') as f:
                        f.write(f"Ojsann, jeg klarte ikke å koble til {ssid}. Sjekk passordet og prøv igjen.")
                    
                    response = {'success': False, 'error': error_msg}
                    print(f"Tilkobling feilet: {error_msg}", flush=True)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except subprocess.TimeoutExpired:
                error_msg = "Tilkobling tok for lang tid (timeout)"
                print(f"Timeout: {error_msg}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': error_msg}).encode())
            except Exception as e:
                error_msg = str(e)
                print(f"Unntak: {error_msg}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': error_msg}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Enkel logging
        print(f"{self.address_string()} - {format % args}")

def cleanup_temp_connections():
    """Fjern gamle temp-connections"""
    try:
        result = subprocess.run(
            ['sudo', 'nmcli', '-t', '-f', 'NAME', 'connection', 'show'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split('\n'):
            conn_name = line.strip()
            if conn_name.startswith('temp-'):
                print(f"Sletter gammel temp connection: {conn_name}", flush=True)
                subprocess.run(['sudo', 'nmcli', 'connection', 'delete', conn_name], 
                             capture_output=True, timeout=5)
    except Exception as e:
        print(f"Cleanup feilet: {e}", flush=True)

if __name__ == '__main__':
    # Rydd opp i gamle temp-connections ved oppstart
    cleanup_temp_connections()
    
    # Hotspot IP (sett i setup-hotspot.sh)
    HOTSPOT_IP = "192.168.50.1"
    
    server = HTTPServer(('0.0.0.0', 80), WiFiHandler)
    print(f"WiFi Setup Portal kjører på http://{HOTSPOT_IP}")
    print("Koble til hotspot 'ChatGPT-Duck' (passord: kvakkkvakk)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutter...")
        server.shutdown()
