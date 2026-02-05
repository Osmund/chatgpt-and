# WiFi-tilkobling via Kontrollpanel - Implementeringsguide

**Dato:** 5. februar 2026  
**Testet på:** Anda (ODuckberry-2)  
**Må implementeres på:** Seven

## Oversikt

Denne oppgraderingen legger til mulighet for å koble til WiFi-nettverk direkte fra Duck kontrollpanelet, uten behov for SSH eller hotspot-portal.

## Funksjoner

- ✅ Klikk på nettverk for å koble til
- ✅ Viser 2.4GHz/5GHz badge på hvert nettverk
- ✅ Uthever aktivt nettverk med grønn bakgrunn
- ✅ Autoconnect settes automatisk ved tilkobling
- ✅ Tilkobling i bakgrunnen (unngår timeout ved nettverksbyte)
- ✅ Håndterer passord med mellomrom og spesialtegn

## Filer som må endres

### 1. `duck-control.py`

Erstatt `/wifi-networks` endpoint (ca linje 392-426):

```python
elif self.path == '/wifi-networks':
    # Hent tilgjengelige WiFi-nettverk
    try:
        # Get active WiFi connection with channel info
        active_result = subprocess.run(
            ['nmcli', '-t', '-f', 'ACTIVE,SSID,CHAN', 'dev', 'wifi'],
            capture_output=True, text=True, timeout=5
        )
        
        active_ssid = None
        active_channel = None
        if active_result.returncode == 0:
            for line in active_result.stdout.strip().split('\n'):
                if line.startswith('yes:'):
                    # Format: yes:SSID:CHANNEL
                    parts = line.split(':')
                    if len(parts) >= 3:
                        active_ssid = parts[1]
                        active_channel = parts[2]
                        break
        
        result = subprocess.run(
            ['sudo', 'nmcli', '-t', '-f', 'SSID,SIGNAL,CHAN,SECURITY', 'dev', 'wifi', 'list'],
            capture_output=True, text=True, timeout=10
        )
        
        networks = []
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        ssid = parts[0]
                        signal = parts[1] if len(parts) > 1 else '0'
                        channel = parts[2] if len(parts) > 2 else ''
                        
                        # Determine frequency band from channel
                        band = ''
                        if channel:
                            try:
                                ch_num = int(channel)
                                if 1 <= ch_num <= 14:
                                    band = '2.4GHz'
                                elif ch_num >= 36:
                                    band = '5GHz'
                            except ValueError:
                                band = ''
                        
                        if ssid and ssid != '--':
                            # Match both SSID and channel to identify the exact active network
                            is_active = (ssid == active_ssid and channel == active_channel)
                            
                            networks.append({
                                'ssid': ssid,
                                'signal': signal + '%',
                                'band': band,
                                'active': is_active
                            })
        
        response = {'status': 'success', 'networks': networks, 'active_ssid': active_ssid}
    except Exception as e:
        response = {'status': 'error', 'networks': [], 'error': str(e)}
    
    self.send_json_response(response, 200)
```

Legg til nytt `/wifi-connect` endpoint (etter `/wifi-networks`):

```python
elif self.path == '/wifi-connect':
    # Koble til WiFi-nettverk
    try:
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        ssid = data.get('ssid', '')
        password = data.get('password', '')
        
        if not ssid:
            self.send_json_response({'success': False, 'error': 'SSID mangler'}, 400)
            return
        
        print(f"Kobler til WiFi: {ssid}", flush=True)
        
        # Send immediate response to avoid timeout
        # Connection will continue in background
        import threading
        
        def connect_in_background():
            try:
                # Rescan for å sikre nettverk er oppdatert
                subprocess.run(['nmcli', 'device', 'wifi', 'rescan'], 
                             capture_output=True, timeout=5)
                
                # Slett eksisterende connection hvis den finnes
                subprocess.run(
                    ['sudo', 'nmcli', 'connection', 'delete', ssid],
                    capture_output=True, timeout=5
                )
                
                # Bruk nmcli device wifi connect
                if password:
                    result = subprocess.run(
                        ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password],
                        capture_output=True, text=True, timeout=30
                    )
                else:
                    result = subprocess.run(
                        ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid],
                        capture_output=True, text=True, timeout=30
                    )
                
                if result.returncode == 0:
                    # Vellykket tilkobling - sett autoconnect
                    subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'modify', ssid, 
                         'connection.autoconnect', 'yes'],
                        capture_output=True, timeout=5
                    )
                    subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'modify', ssid, 
                         'connection.autoconnect-priority', '10'],
                        capture_output=True, timeout=5
                    )
                    print(f"✓ Koblet til {ssid} med autoconnect", flush=True)
                else:
                    error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                    print(f"✗ Tilkobling feilet: {error_msg}", flush=True)
            except Exception as e:
                print(f"✗ Background connection exception: {e}", flush=True)
        
        # Start connection in background
        thread = threading.Thread(target=connect_in_background, daemon=True)
        thread.start()
        
        # Send immediate success response
        response = {
            'success': True, 
            'message': f'Tilkobling startet! Sjekk nettverkslisten om noen sekunder.'
        }
        self.send_json_response(response, 200)
        
    except Exception as e:
        print(f"Exception ved WiFi-tilkobling: {e}", flush=True)
        import traceback
        traceback.print_exc()
        self.send_json_response({'success': False, 'error': str(e)}, 500)
```

### 2. `templates/app.js`

Erstatt `getWiFiNetworks()` funksjon (ca linje 257):

```javascript
async function getWiFiNetworks() {
    const listDiv = document.getElementById('wifi-list');
    listDiv.textContent = 'Skanner etter nettverk...';
    
    try {
        const response = await fetch('/wifi-networks');
        const data = await response.json();
        
        if (data.status === 'success' && data.networks) {
            if (data.networks.length === 0) {
                listDiv.textContent = 'Ingen nettverk funnet';
            } else {
                listDiv.innerHTML = '<ul style="list-style: none; padding: 0;">' + 
                    data.networks.map(net => {
                        const bandBadge = net.band ? `<span style="margin-left: 8px; padding: 2px 6px; background: ${net.band === '5GHz' ? '#4caf50' : '#2196f3'}; color: white; border-radius: 3px; font-size: 0.85em; font-weight: bold;">${net.band}</span>` : '';
                        const activeIndicator = net.active ? '<span style="margin-left: 8px; color: #4caf50; font-weight: bold;">✓ Tilkoblet</span>' : '';
                        const bgColor = net.active ? '#e8f5e9' : '#f5f5f5';
                        const hoverColor = net.active ? '#c8e6c9' : '#e0e0e0';
                        const borderLeft = net.active ? 'border-left: 4px solid #4caf50;' : '';
                        
                        return `
                        <li style="padding: 10px; margin: 5px 0; background: ${bgColor}; border-radius: 5px; cursor: pointer; transition: background 0.2s; ${borderLeft}"
                            onclick="connectToWifi('${net.ssid.replace(/'/g, "\\'")}')"
                            onmouseover="this.style.background='${hoverColor}'"
                            onmouseout="this.style.background='${bgColor}'">
                            📶 ${net.ssid} (${net.signal})${bandBadge}${activeIndicator}
                        </li>
                    `}).join('') + 
                    '</ul>';
            }
        } else {
            listDiv.textContent = 'Kunne ikke hente nettverk';
        }
    } catch (error) {
        listDiv.textContent = 'Feil: ' + error.message;
    }
}
```

Legg til ny `connectToWifi()` funksjon (etter `getWiFiNetworks()`):

```javascript
async function connectToWifi(ssid) {
    const password = prompt(`Skriv inn passord for "${ssid}"\n\n(La felt stå tomt for åpne nettverk):`);
    
    if (password === null) {
        return; // User cancelled
    }
    
    // Show connecting message immediately
    const connectingMsg = `⏳ Kobler til "${ssid}"...\n\nDette kan ta 10-30 sekunder.\nAndas kontrollpanel kan bli utilgjengelig midlertidig hvis hun bytter nettverk.`;
    
    // Use a non-blocking alert alternative
    const statusDiv = document.createElement('div');
    statusDiv.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.9); color: white; padding: 30px; border-radius: 10px; z-index: 10000; text-align: center; max-width: 400px;';
    statusDiv.innerHTML = `<div style="font-size: 24px; margin-bottom: 15px;">⏳</div><div>${connectingMsg.replace(/\n/g, '<br>')}</div>`;
    document.body.appendChild(statusDiv);
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000); // 45 second timeout
        
        const response = await fetch('/wifi-connect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ssid: ssid,
                password: password
            }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        document.body.removeChild(statusDiv);
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Koblet til "${ssid}"!\n\n${data.message || 'Tilkobling vellykket'}`);
            // Refresh network list after connection
            setTimeout(() => getWiFiNetworks(), 2000);
        } else {
            alert(`❌ Kunne ikke koble til "${ssid}"\n\n${data.error || 'Ukjent feil'}`);
        }
    } catch (error) {
        document.body.removeChild(statusDiv);
        
        if (error.name === 'AbortError') {
            // Timeout - connection might still be in progress
            alert(`⏱️ Tilkobling til "${ssid}" tok for lang tid.\n\nTilkoblingen kan fortsatt være i gang. Sjekk nettverkslisten om noen sekunder for å se om den lyktes.`);
            setTimeout(() => getWiFiNetworks(), 5000);
        } else {
            alert('❌ Nettverksfeil: ' + error.message + '\n\nDette er normalt hvis Anda byttet nettverk. Prøv å refreshe siden om noen sekunder.');
        }
        
        // Try to refresh network list anyway
        setTimeout(() => {
            try {
                getWiFiNetworks();
            } catch (e) {
                console.log('Could not refresh network list:', e);
            }
        }, 5000);
    }
}
```

## Implementeringssteg

1. **Backup**: Ta backup av `duck-control.py` og `templates/app.js` på Seven
2. **Kopier endringer**: Implementer endringene over i de to filene
3. **Test**: Restart duck-control service og test funksjonaliteten
4. **Verifiser**: Sjekk at nettverkslisten viser 2.4GHz/5GHz badges og aktiv nettverk-indikator

## Testing

```bash
# Restart service
sudo systemctl restart duck-control.service

# Åpne kontrollpanel
http://seven.local:3000

# Test:
1. Sjekk at WiFi-liste viser nettverk med 2.4GHz/5GHz badges
2. Sjekk at aktivt nettverk er uthevet med grønn bakgrunn
3. Klikk på et nettverk, skriv inn passord, verifiser tilkobling
4. Refresh siden og sjekk at nytt nettverk vises som aktivt
```

## Viktige notater

- **Threading**: Backend bruker threading for å unngå timeout ved nettverksbyte
- **SSID vs Channel**: To nettverk med samme navn skilles ved hjelp av kanal-nummer
- **Autoconnect**: Settes automatisk til `yes` med priority `10` (høyere enn hotspot: `-10`)
- **Feilhåndtering**: Frontend har 45 sekunders timeout og gir tydelige feilmeldinger

## Troubleshooting

**Problem**: "Load failed" ved tilkobling  
**Løsning**: Dette er normalt hvis Duck bytter nettverk. Refresh siden etter 5-10 sekunder.

**Problem**: Begge 5GHz og 2.4GHz nettverk vises som aktive  
**Løsning**: Verifiser at channel-matching fungerer i `/wifi-networks` endpoint.

**Problem**: Kan ikke koble til nettverk med mellomrom i passord  
**Løsning**: Backend bruker subprocess.run med array, ikke shell - skulle fungere automatisk.

## Support

Ved problemer, sjekk logs:
```bash
sudo journalctl -u duck-control.service -n 100 -f
```
