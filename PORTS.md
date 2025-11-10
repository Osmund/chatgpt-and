# Nettverks- og Port-konfigurasjon

## 🔌 Aktive porter

### Port 3000 - Duck Control Panel (Web Interface)

**Formål**: Hovedkontrollpanel for ChatGPT Duck-systemet

**Status**: Alltid tilgjengelig når `duck-control.service` kjører

**Funksjoner**:
- 🎮 Service-kontroll (start/stopp/restart)
- 📊 Sanntids status og systemlogger
- 🤖 AI-konfigurasjon (modell, personlighet)
- 🗣️ Stemme- og lydinnstillinger (voice, volum, hastighet)
- 👄 Nebb-kontroll og testing
- 💬 Send meldinger direkte til anda
- 📱 WiFi-administrasjon og nettverksscanning
- 🔧 System-administrasjon (reboot/shutdown)

**Tilgang**:
```
Lokalt nettverk:  http://<pi-ip>:3000
Hostname:         http://oduckberry:3000
Localhost (Pi):   http://localhost:3000

Eksempel:         http://192.168.1.100:3000
```

**Service**: `duck-control.service`
```bash
sudo systemctl status duck-control.service
sudo journalctl -u duck-control.service -f
```

**Teknisk detalj**:
- Python BaseHTTPRequestHandler
- Ingen eksterne web-dependencies
- Single-page application (embedded HTML/CSS/JS)
- AJAX/fetch API for async kommunikasjon
- Auto-refresh status hvert 5. sekund

---

### Port 80 - WiFi Configuration Portal

**Formål**: WiFi-oppsett når Pi er i hotspot-modus

**Status**: Kun tilgjengelig når hotspot er aktivert

**Funksjoner**:
- 📡 Scanne tilgjengelige WiFi-nettverk
- 🔐 Koble til nytt WiFi med passord
- ✅ Verifisere tilkobling
- 🔄 Automatisk switch til client-mode ved vellykket tilkobling

**Tilgang når hotspot er aktivt**:
1. Koble enheten din til hotspot: `ChatGPT-Duck`
   - Passord: `kvakkkvakk`
2. Åpne nettleser, gå til:
   - `http://10.42.0.1`
   - `http://oduckberry`
   - De fleste enheter åpner portalen automatisk (captive portal)

**Service**: `auto-hotspot.service`
```bash
sudo systemctl status auto-hotspot.service
```

**Teknisk detalj**:
- Python HTTP server (wifi-portal.py)
- NetworkManager integration for WiFi-scanning
- Captive portal detection for automatisk åpning

---

## 🌐 Utgående forbindelser

### OpenAI API
- **Host**: `api.openai.com`
- **Port**: 443 (HTTPS)
- **Protokoll**: REST API over TLS
- **Brukes til**: ChatGPT AI-responser
- **Latency**: ~1-3 sekunder per request

### Azure Speech Services
- **Host**: `<region>.tts.speech.microsoft.com`
- **Host**: `<region>.stt.speech.microsoft.com`
- **Port**: 443 (HTTPS)
- **Protokoll**: REST API og WebSocket over TLS
- **Brukes til**: 
  - Text-to-Speech (TTS) - norsk tale
  - Speech-to-Text (STT) - stemmegjenkjenning
- **Latency**: ~0.5-1.5 sekunder per request

### NTP (Network Time Protocol)
- **Port**: 123 (UDP)
- **Brukes til**: Tidssynkronisering (automatisk av systemet)

---

## 🔧 GPIO Pins (ikke nettverks-porter)

Dokumentert her for fullstendighetens skyld:

### RGB LED
```
Pin 11 (GPIO 17) → Red
Pin 13 (GPIO 27) → Green
Pin 15 (GPIO 22) → Blue
Pin 6/9/14 (GND) → Ground
```

### Servo (nebb)
```
Pin 8 (GPIO 14)  → Signal (PWM)
External 5V      → VCC
Shared Ground    → Ground
```

---

## 🔒 Brannmur og sikkerhet

### Anbefalt brannmur-konfigurasjon (ufw)

```bash
# Installer ufw hvis ikke installert
sudo apt-get install ufw

# Tillat SSH (viktig!)
sudo ufw allow 22/tcp

# Tillat kontrollpanel fra lokalt nettverk
sudo ufw allow from 192.168.1.0/24 to any port 3000

# Hvis du vil åpne for alle (ikke anbefalt)
# sudo ufw allow 3000/tcp

# Aktiver brannmur
sudo ufw enable

# Sjekk status
sudo ufw status verbose
```

### Port forwarding (for ekstern tilgang)

⚠️ **Ikke anbefalt uten ekstra sikkerhet!**

Hvis du vil ha tilgang utenfra hjemmenettet:
1. Bruk VPN (WireGuard, Tailscale) - **anbefalt metode**
2. Eller: Port forward 3000 i routeren
3. Legg til basic authentication i duck-control.py
4. Bruk HTTPS med Let's Encrypt

**Eksempel med Tailscale** (enkleste):
```bash
# Installer Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Koble til Tailscale-nettverket
sudo tailscale up

# Få Tailscale IP
tailscale ip -4

# Tilgang fra hvor som helst: http://<tailscale-ip>:3000
```

---

## 📊 Port-bruk oversikt

| Port | Service | Protokoll | Tilgang | Påkrevd |
|------|---------|-----------|---------|---------|
| 3000 | duck-control | HTTP | Lokalt nettverk | Ja (for web UI) |
| 80 | wifi-portal | HTTP | Hotspot-klienter | Nei (kun for WiFi-setup) |
| 22 | SSH | TCP | Lokalt/Remote | Nei (men nyttig) |
| 443 | HTTPS (utgående) | TCP | Internet | Ja (for APIs) |
| 123 | NTP (utgående) | UDP | Internet | Nei (men nyttig) |

---

## 🐛 Feilsøking

### Port 3000 er ikke tilgjengelig

**Diagnose**:
```bash
# Sjekk om service kjører
sudo systemctl status duck-control.service

# Sjekk om noe lytter på port 3000
sudo netstat -tulpn | grep 3000

# Eller med ss
sudo ss -tulpn | grep 3000

# Test lokalt
curl http://localhost:3000
```

**Løsning**:
```bash
# Start service
sudo systemctl start duck-control.service

# Sjekk logger for feil
sudo journalctl -u duck-control.service -n 50

# Hvis port er opptatt, finn prosessen
sudo lsof -i :3000
# Kill prosessen hvis nødvendig
sudo kill <PID>
```

### Kan ikke nå kontrollpanel fra annen enhet

**Diagnose**:
```bash
# Finn Pi's IP
hostname -I

# Sjekk at duck-control lytter på alle interfaces (0.0.0.0)
sudo netstat -tulpn | grep 3000
# Skal vise: 0.0.0.0:3000 (ikke 127.0.0.1:3000)

# Test fra Pi selv
curl http://localhost:3000

# Ping fra annen enhet
ping <pi-ip>
```

**Løsning**:
1. Sjekk at begge enheter er på samme nettverk
2. Sjekk brannmur (disable midlertidig for test):
   ```bash
   sudo ufw disable
   # Test tilgang
   # Hvis det funker, legg til regel:
   sudo ufw allow 3000/tcp
   sudo ufw enable
   ```
3. Sjekk at duck-control.py binder til `0.0.0.0` (ikke `127.0.0.1`)

### WiFi-portal fungerer ikke

**Diagnose**:
```bash
# Sjekk om hotspot er aktivt
nmcli device status

# Sjekk om wifi-portal kjører
ps aux | grep wifi-portal

# Sjekk IP på hotspot interface
ip addr show ap0
```

**Løsning**:
```bash
# Start hotspot manuelt
sudo ./auto-hotspot.sh

# Eller via kontrollpanel
# Klikk "Bytt til hotspot-modus"
```

---

## 📚 Relatert dokumentasjon

- [INSTALL.md](INSTALL.md) - Komplett installasjonsveiledning
- [ARCHITECTURE.md](ARCHITECTURE.md) - Teknisk arkitektur
- [README.md](README.md) - Hovedveiledning

---

**Sist oppdatert**: 10. november 2025
