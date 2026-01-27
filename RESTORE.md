# Anda Restore Guide 🦆

**Komplett guide for å gjenopprette Anda fra bunnen av etter katastrofe.**

---

## 📋 Oversikt

Denne guiden tar deg gjennom:
1. Flash Raspberry Pi OS på nytt SD-kort
2. Grunnleggende Pi-oppsett
3. Installere rclone og koble til OneDrive
4. Clone siste versjon fra GitHub
5. Hente ned backup (database og konfigurasjon)
6. Installere alle dependencies
7. Sette opp services
8. Verifisere at alt fungerer

**Estimert tid: 30-45 minutter**

---

## 🚨 Forutsetninger

- [ ] Nytt SD-kort (minimum 16 GB, anbefalt 32 GB)
- [ ] PC/Mac med SD-kortleser
- [ ] Raspberry Pi Imager installert på PC
- [ ] Internettforbindelse (via Ethernet eller WiFi)
- [ ] OneDrive-konto med Anda-backup

---

## 📝 Del 1: Flash Raspberry Pi OS

### 1.1 Last ned Raspberry Pi Imager
```
Windows/Mac/Linux: https://www.raspberrypi.com/software/
```

### 1.2 Flash SD-kort
1. **Åpne Raspberry Pi Imager**
2. **Choose OS:**
   - `Raspberry Pi OS (other)`
   - Velg: `Raspberry Pi OS (64-bit)` (IKKE Lite, trenger desktop for første oppsett)
3. **Choose Storage:**
   - Velg ditt SD-kort
4. **Settings (⚙️ ikon):**
   - **Hostname:** `oduckberry` (eller annet navn)
   - **Enable SSH:** ✅ Use password authentication
   - **Username:** `admog`
   - **Password:** `[ditt passord]`
   - **Configure WiFi:** ✅
     - SSID: `[ditt WiFi-navn]`
     - Password: `[ditt WiFi-passord]`
     - Country: `NO`
   - **Locale:** 
     - Timezone: `Europe/Oslo`
     - Keyboard: `no`
5. **Skriv til SD-kort** (tar 5-10 min)
6. **Sett SD-kort i Raspberry Pi og slå på**

### 1.3 Finn Pi på nettverket
```bash
# Fra PC/Mac terminal:
ping oduckberry.local

# Eller finn IP fra router
# Eller bruk: arp -a | grep raspberry
```

### 1.4 SSH inn til Pi
```bash
ssh admog@oduckberry.local
# Eller: ssh admog@[IP-adresse]
```

---

## 🔧 Del 2: Grunnleggende Pi-oppsett

### 2.1 Oppdater systemet
```bash
sudo apt update
sudo apt upgrade -y
# Dette tar 10-15 minutter første gang
```

### 2.2 Installer grunnleggende verktøy
```bash
sudo apt install -y \
    git \
    curl \
    wget \
    vim \
    htop \
    screen
```

---

## ☁️ Del 3: Installere rclone og koble til OneDrive

### 3.1 Installer nyeste rclone
```bash
curl https://rclone.org/install.sh | sudo bash
```

### 3.2 Konfigurer OneDrive
```bash
rclone config
```

**Følg disse stegene nøye:**

1. `n` - New remote
2. **name:** `anda-backup`
3. **Storage:** `onedrive` (finn nummer i listen, vanligvis 31)
4. **client_id:** [Trykk bare Enter]
5. **client_secret:** [Trykk bare Enter]
6. **region:** `1` (Microsoft Cloud Global)
7. **Edit advanced config:** `n` (No)
8. **Use auto config:** `n` (No - fordi Pi ikke har browser)

**Nå vil rclone gi deg:**
```
For this to work, you will need rclone available on a machine that has
a web browser available.

For more help and alternate methods see: https://rclone.org/remote_setup/

Execute the following on the machine with the web browser:
    rclone authorize "onedrive"
```

### 3.3 Godkjenn på annen maskin
**På din PC/Mac (må ha rclone installert):**
```bash
# Installer rclone hvis ikke allerede gjort:
# Mac: brew install rclone
# Windows: Bruk Chocolatey eller last ned fra rclone.org

rclone authorize "onedrive"
```

- Browser åpner automatisk
- Logg inn med Microsoft-konto
- Godkjenn tilgang
- **Kopiér hele token-teksten** som vises i terminalen
  (Starter med `{"access_token":...}`)

### 3.4 Lim inn token på Pi
- Gå tilbake til SSH-vinduet på Pi
- Lim inn hele token-teksten
- Trykk Enter

### 3.5 Velg OneDrive-drive
- Velg `1` (OneDrive personal - den første i listen)
- `y` - Yes, this is OK
- `q` - Quit config

### 3.6 Test tilkobling
```bash
rclone lsd anda-backup:
# Skal vise mapper i din OneDrive
```

---

## 📦 Del 4: Clone fra GitHub og hent backup

### 4.1 Clone repository
```bash
mkdir -p ~/Code
cd ~/Code
git clone https://github.com/[DIN_GITHUB_BRUKER]/chatgpt-and.git
cd chatgpt-and
```

**Tips:** Hvis du ikke husker GitHub-URL:
- Gå til https://github.com/[bruker]/chatgpt-and
- Klikk grønn "Code" knapp
- Kopier HTTPS URL

### 4.2 Se tilgjengelige backups
```bash
rclone lsf anda-backup:duck-backups/Samantha/ --dirs-only
```

Eksempel output:
```
2026-01-27_21-30-58/
2026-01-24_03-00-00/
2026-01-22_03-00-00/
```

### 4.3 Hent siste backup
```bash
# Finn nyeste backup (første i listen)
LATEST_BACKUP=$(rclone lsf anda-backup:duck-backups/Samantha/ --dirs-only | sort -r | head -n1 | tr -d '/')

echo "Henter backup: $LATEST_BACKUP"

# Last ned database
rclone copy "anda-backup:duck-backups/Samantha/$LATEST_BACKUP/duck_memory.db" ~/Code/chatgpt-and/

# Last ned .env (API keys og konfigurasjon)
rclone copy "anda-backup:duck-backups/Samantha/$LATEST_BACKUP/.env" ~/Code/chatgpt-and/

# Last ned systemd services
mkdir -p /tmp/systemd-backup
rclone copy "anda-backup:duck-backups/Samantha/$LATEST_BACKUP/systemd/" /tmp/systemd-backup/

echo "✓ Backup hentet!"
ls -lh ~/Code/chatgpt-and/duck_memory.db
ls -lh ~/Code/chatgpt-and/.env
```

### 4.4 Verifiser filer
```bash
# Database skal være ~9 MB
ls -lh ~/Code/chatgpt-and/duck_memory.db

# .env skal inneholde API keys
cat ~/Code/chatgpt-and/.env | grep -E "OPENAI|AZURE|PICOVOICE"
```

**VIKTIG:** Sjekk at `.env` inneholder alle nødvendige API keys!

---

## 🐍 Del 5: Installere Python dependencies

### 5.1 Installer systembiblioteker
```bash
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    portaudio19-dev \
    python3-pyaudio \
    espeak \
    ffmpeg \
    sox \
    libsox-fmt-all \
    sqlite3 \
    alsa-utils \
    pigpio \
    python3-pigpio
```

### 5.2 Installer Python packages
```bash
cd ~/Code/chatgpt-and
pip3 install -r requirements.txt --break-system-packages
```

**Dette tar 5-10 minutter** og installerer:
- openai, azure-cognitiveservices-speech
- pvporcupine (wake word detection)
- Flask, requests, dotenv
- homeassistant-api, twilio
- numpy, tiktoken

---

## 🔊 Del 6: Konfigurer audio (MAX98357A)

### 6.1 Kjør audio setup-script
```bash
cd ~/Code/chatgpt-and
bash setup_max98357a.sh
```

Dette scriptet:
- Aktiverer I2S i `/boot/firmware/config.txt`
- Setter opp ALSA-konfigurasjon
- Konfigurerer default audio output

### 6.2 Reboot for å aktivere I2S
```bash
sudo reboot
```

**Vent 1 minutt, SSH inn igjen:**
```bash
ssh admog@oduckberry.local
```

### 6.3 Test audio
```bash
speaker-test -t wav -c 2 -l 1
```

**Forventet output:**
```
Speaker test 1.2.8
...
Front Left
Front Right
```

**Hvis ingen lyd:**
```bash
# Sjekk lydkort
aplay -l

# Hvis MAX98357A ikke vises, kjør setup_max98357a.sh igjen
cd ~/Code/chatgpt-and
bash setup_max98357a.sh
sudo reboot
```

---

## ⚙️ Del 7: Installere systemd services

### 7.1 Kopier services fra backup
```bash
sudo cp /tmp/systemd-backup/*.service /etc/systemd/system/
sudo cp /tmp/systemd-backup/*.timer /etc/systemd/system/

# Alternativt, hvis backup mangler:
sudo cp ~/Code/chatgpt-and/*.service /etc/systemd/system/
sudo cp ~/Code/chatgpt-and/*.timer /etc/systemd/system/
```

### 7.2 Start pigpiod (for servo/GPIO)
```bash
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

### 7.3 Reload og aktiver Anda-services
```bash
sudo systemctl daemon-reload

# Aktiver alle services
sudo systemctl enable chatgpt-duck.service
sudo systemctl enable duck-control.service
sudo systemctl enable fan-control.service
sudo systemctl enable auto-hotspot.service
sudo systemctl enable anda-backup.timer

# Start hovedservices
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service
sudo systemctl start fan-control.service
```

### 7.4 Start backup timer
```bash
sudo systemctl start anda-backup.timer
```

---

## ✅ Del 8: Verifisere installasjon

### 8.1 Sjekk service status
```bash
# Hovedservice (Anda)
sudo systemctl status chatgpt-duck.service

# Kontrollpanel
sudo systemctl status duck-control.service

# Vifte
sudo systemctl status fan-control.service

# Backup timer
sudo systemctl status anda-backup.timer
```

**Forventet:** Alle skal vise `active (running)` eller `active (waiting)` for timer

### 8.2 Sjekk logger
```bash
# Anda-logger (siste 50 linjer)
journalctl -u chatgpt-duck.service -n 50

# Følg logger live
journalctl -u chatgpt-duck.service -f
```

**Hva å se etter:**
- ✅ `Listening for wake word...`
- ✅ `Connected to Home Assistant`
- ✅ `Database initialized`
- ❌ Ingen `ERROR` eller `Exception` meldinger

### 8.3 Test kontrollpanel
```bash
# Finn Pi sin IP
hostname -I
```

**Åpne i browser på PC:**
```
http://oduckberry.local:3000
# eller
http://[IP-ADRESSE]:3000
```

**Skal vise:**
- 🦆 ChatGPT Duck Control Panel
- Status: "Running" (grønn)
- Nåværende bruker
- Home Assistant status
- Alle kontroller fungerer

### 8.4 Test wake word
**Si til Pi:**
```
"Samantha" [vent på beep] "Hallo!"
```

**Forventet:**
- Pi detekterer "Samantha"
- Spiller beep-lyd
- Lytter til kommando
- Svarer med stemme

### 8.5 Test backup
```bash
# Manuell backup-test
cd ~/Code/chatgpt-and
bash backup-anda.sh
```

**Forventet output:**
```
==============================================================================
  Anda Backup - Samantha
==============================================================================
...
✓ Backup completed successfully!
```

**Verifiser i OneDrive:**
```bash
rclone lsf anda-backup:duck-backups/Samantha/ --dirs-only
# Skal vise ny backup med dagens dato
```

---

## 🎯 Del 9: Endelig konfigurasjon

### 9.1 Verifiser alle API keys i .env
```bash
cd ~/Code/chatgpt-and
nano .env
```

**Sjekk at disse er satt:**
- `DUCK_NAME=Samantha`
- `OPENAI_API_KEY=sk-proj-...`
- `AZURE_TTS_KEY=...`
- `AZURE_STT_KEY=...`
- `PICOVOICE_API_KEY=...`
- `HA_TOKEN=...`
- `HA_URL=http://...`
- `TWILIO_ACCOUNT_SID=...`
- `TWILIO_AUTH_TOKEN=...`

### 9.2 Restart services for å laste ny config
```bash
sudo systemctl restart chatgpt-duck.service
sudo systemctl restart duck-control.service
```

### 9.3 Sett opp automatisk backup
```bash
# Backup timer kjører automatisk hver mandag, onsdag og fredag kl 03:00
# Se neste kjøring:
systemctl list-timers anda-backup.timer
```

---

## 📚 Vedlegg: Feilsøking

### Problem: "No module named 'openai'"
**Løsning:**
```bash
cd ~/Code/chatgpt-and
pip3 install -r requirements.txt --break-system-packages
```

### Problem: "Audio device not found"
**Løsning:**
```bash
# Sjekk at I2S er aktivert
grep "dtoverlay=hifiberry-dac" /boot/firmware/config.txt

# Kjør setup på nytt
bash setup_max98357a.sh
sudo reboot
```

### Problem: "Wake word not detecting"
**Løsning:**
```bash
# Sjekk mikrofon
arecord -l

# Test opptak
arecord -d 5 test.wav
aplay test.wav

# Sjekk Porcupine API key
cat .env | grep PICOVOICE_API_KEY

# Verifiser at .ppn wake word filer eksisterer
ls -lh ~/Code/chatgpt-and/*.ppn
ls -lh ~/Code/chatgpt-and/porcupine/*.ppn
```

### Problem: "Home Assistant connection failed"
**Løsning:**
```bash
# Test forbindelse
curl -H "Authorization: Bearer [HA_TOKEN]" http://[HA_URL]/api/

# Sjekk at token er gyldig i Home Assistant:
# Settings → Profile → Long-Lived Access Tokens
```

### Problem: "Database locked"
**Løsning:**
```bash
# Stopp service
sudo systemctl stop chatgpt-duck.service

# Sjekk at ingen prosesser bruker database
lsof ~/Code/chatgpt-and/duck_memory.db

# Start på nytt
sudo systemctl start chatgpt-duck.service
```

### Problem: "Backup fails: unauthenticated"
**Løsning:**
```bash
# Slett rclone config og sett opp på nytt
rclone config delete anda-backup
rclone config
# Følg setup-stegene igjen
```

---

## 📋 Sjekkliste: Er alt OK?

- [ ] Raspberry Pi OS installert og oppdatert
- [ ] SSH fungerer
- [ ] rclone konfigurert med OneDrive
- [ ] GitHub repository cloned
- [ ] Database (`duck_memory.db`) hentet fra backup (9 MB)
- [ ] `.env` fil hentet fra backup og verifisert
- [ ] Python packages installert (`requirements.txt`)
- [ ] Audio fungerer (MAX98357A oppsett)
- [ ] Porcupine wake word detection fungerer
- [ ] Alle systemd services installert og enabled
- [ ] `chatgpt-duck.service` kjører uten feil
- [ ] `duck-control.service` kjører (port 3000)
- [ ] Kontrollpanel tilgjengelig i browser
- [ ] Wake word "Samantha" fungerer
- [ ] Anda svarer med stemme
- [ ] Backup timer aktivert (3x per uke)
- [ ] Manuell backup testet og fungerer

---

## 🚀 Ferdig!

**Anda er nå fullstendig gjenopprettet!**

- Alle minner bevart fra backup
- Alle API-integrasjoner fungerer
- Automatisk backup aktiv (man/ons/fre kl 03:00)
- Kan ta manuell backup via kontrollpanel

**Neste steg:**
- Test alle funksjoner (wake word, Home Assistant, SMS, etc)
- Verifiser at personlighet er intakt
- La Anda kjøre noen timer og sjekk logger for feil

**Viktige kommandoer:**
```bash
# Se logger live
journalctl -u chatgpt-duck.service -f

# Restart Anda
sudo systemctl restart chatgpt-duck.service

# Sjekk status
sudo systemctl status chatgpt-duck.service

# Manuell backup
bash ~/Code/chatgpt-and/backup-anda.sh

# Se backups i OneDrive
rclone lsf anda-backup:duck-backups/Samantha/
```

**Moro deg med Anda! 🦆**
