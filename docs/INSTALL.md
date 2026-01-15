# ChatGPT Duck - Installasjonsveiledning

Komplett guide for å sette opp ChatGPT Duck fra bunnen av.

## Forutsetninger

- **Raspberry Pi** (4, 5, eller 400) med minimum 2GB RAM
- **MicroSD-kort** (minimum 16GB, anbefalt 32GB)
- **Raspberry Pi OS** (Bookworm eller nyere)
- **Internett-tilkobling** (WiFi eller ethernet)
- **Mikrofon** (USB eller HAT)
- **Høyttaler** (3.5mm, HDMI, eller USB)

## Del 1: Hardware-oppsett

### 1.1 RGB LED (Monk Makes eller lignende)

```
RGB LED    →   Raspberry Pi GPIO
───────────────────────────────────
Red (R)    →   GPIO 17 (pin 11)
Green (G)  →   GPIO 27 (pin 13)
Blue (B)   →   GPIO 22 (pin 15)
Ground (–) →   Ground (pin 6, 9, 14, 20, 25, 30, 34, 39)
```

**Test RGB LED**:
```bash
# Test rød
python3 -c "from gpiozero import LED; led = LED(17); led.on(); input('Press Enter'); led.off()"

# Test grønn
python3 -c "from gpiozero import LED; led = LED(27); led.on(); input('Press Enter'); led.off()"

# Test blå
python3 -c "from gpiozero import LED; led = LED(22); led.on(); input('Press Enter'); led.off()"
```

### 1.2 Servo (nebb-bevegelse)

⚠️ **KRITISK**: Servo MÅ ha separat strømforsyning via USB-C PD-trigger!

```
PCA9685        →   Tilkobling
───────────────────────────────────
VCC (logikk)   →   3.3V (Pi pin 1 eller 17)
GND            →   Ground (Pi pin 6, 9, etc)
SDA            →   GPIO2 (pin 3)
SCL            →   GPIO3 (pin 5)
V+ (servo)     →   USB-C PD-trigger 5V output
GND (servo)    →   USB-C PD-trigger GND (koblet til Pi GND)
Servo CH0      →   Nebb-servo signal
```

**USB-C PD-trigger oppsett:**
```
USB-C PD-trigger    →   Tilkobling
─────────────────────────────────────
USB-C input         →   Pi USB-C port (via avklippet kabel)
5V output (+)       →   PCA9685 V+
GND output (-)      →   PCA9685 GND + Pi GND (felles ground)
```

### 1.3 Vifte (5V kjøling - valgfritt)

```
Vifte      →   Raspberry Pi GPIO
───────────────────────────────────
Blå        →   GPIO 13 (pin 33)
Svart      →   Ground (pin 6, 9, 14, 20, 25, 30, 34, 39)
```

**Automatisk kjøling**:
- Starter ved CPU-temperatur ≥ 55°C
- Stopper ved CPU-temperatur ≤ 50°C
- Kan overstyres manuelt via kontrollpanel

**Hvorfor separat strøm?**
- Servos kan trekke 1-2A under bevegelse
- Pi's 5V pin kan kun levere ~1A total
- Delt strøm gir voltage drops → Pi rebooter

**Anbefalt oppsett med USB-C PD-trigger**:
```
┌──────────────┐  USB-C        ┌─────────────────┐
│   Raspberry  │  (avklippet   │  USB-C PD       │
│     Pi       ├───────────────┤  Trigger        │
│              │  kabel)       │  Module         │
│              │               └────┬──────┬─────┘
│  GPIO2/3     │                    │      │
│  (I2C)       ├───────┐            │5V    │GND
│              │       │            │      │
│   Ground     │       │            │      │
└──────┬───────┘       │            │      │
       │               │            │      │
       │               ▼            ▼      │
       │       ┌───────────────────────┐   │
       │       │      PCA9685          │   │
       │       │   Servo Controller    │   │
       │       │  VCC=3.3V  V+=5V      │   │
       │       └──────┬────────────────┘   │
       │              │ Servo CH0          │
       │              ▼                    │
       │       ┌─────────────┐             │
       │       │   Servo     │             │
       │       │ (SG90/MG90) │             │
       │       └─────────────┘             │
       │                                   │
       └───────────────────────────────────┘
         (Felles Ground)
```

**Test servo**:
```bash
python3 -c "from gpiozero import Servo; s = Servo(14); s.mid(); input('Press Enter'); s.max(); input('Press Enter'); s.min(); input('Press Enter')"
```

### 1.3 Audio-oppsett

**Test mikrofon**:
```bash
# List audio devices
arecord -l

# Test recording (10 sekunder)
arecord -D hw:1,0 -d 10 -f cd test.wav
aplay test.wav
```

**Test høyttaler**:
```bash
# Test output
speaker-test -t wav -c 2

# Adjust volume
alsamixer
```

**Sett default audio device** (hvis nødvendig):
```bash
# Edit ~/.asoundrc
cat > ~/.asoundrc << 'EOF'
pcm.!default {
    type hw
    card 1
}

ctl.!default {
    type hw
    card 1
}
EOF
```

## Del 2: Software-installasjon

### 2.1 System-pakker

```bash
# Oppdater system
sudo apt-get update
sudo apt-get upgrade -y

# Installer nødvendige pakker
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    portaudio19-dev \
    libportaudio2 \
    ffmpeg \
    git \
    curl \
    wget \
    unzip \
    alsa-utils \
    libasound2-dev \
    network-manager
```

### 2.2 Klon repository

```bash
cd ~
mkdir -p Code
cd Code
git clone https://github.com/Osmund/chatgpt-and.git
cd chatgpt-and
```

### 2.3 Python virtual environment

```bash
# Opprett venv
python3 -m venv .venv

# Aktiver venv
source .venv/bin/activate

# Oppgrader pip
pip install --upgrade pip

# Installer dependencies
pip install -r requirements.txt
```

**Troubleshooting pyaudio**:
```bash
# Hvis pyaudio feiler
sudo apt-get install portaudio19-dev python3-pyaudio
pip install --upgrade pyaudio

# Alternativt: build fra source
pip install --no-binary :all: pyaudio
```

### 2.4 Picovoice API-nøkkel

Porcupine wake word detection krever en gratis API-nøkkel fra Picovoice:

1. Gå til https://console.picovoice.ai/
2. Opprett gratis konto
3. Kopier Access Key
4. Legg til i `.env` filen (se Del 3)

**Note**: Porcupine-modellen (`porcupine/samantha_en_raspberry-pi_v4_0_0.ppn`) er allerede inkludert i prosjektet.

## Del 3: API-nøkler

### 3.1 OpenAI API Key

1. Gå til https://platform.openai.com/api-keys
2. Logg inn eller opprett konto
3. Klikk "Create new secret key"
4. Kopier nøkkelen (format: `sk-...`)

**Pricing** (november 2025):
- gpt-3.5-turbo: ~$0.002 per 1K tokens
- gpt-4-turbo: ~$0.01 per 1K tokens
- Estimert kostnad: $0.10-0.50 per dag med normal bruk

### 3.2 Azure Speech Service

1. Gå til https://portal.azure.com
2. Opprett "Cognitive Services" eller "Speech Service"
3. Velg region (anbefalt: `westeurope` eller `northeurope`)
4. Velg pricing tier (F0 = gratis tier, eller S0 = betalt)
5. Noter:
   - **Key 1** (API-nøkkel)
   - **Region** (f.eks. `westeurope`)

**Free tier limits**:
- TTS: 0.5M characters/month gratis
- STT: 5 audio hours/month gratis
- Mer enn nok for personlig bruk

### 3.3 Opprett .env-fil

```bash
cd /home/admog/Code/chatgpt-and

cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-openai-key-here
AZURE_TTS_KEY=your-azure-tts-key-here
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=your-azure-stt-key-here
AZURE_STT_REGION=westeurope
PICOVOICE_API_KEY=your-picovoice-key-here
EOF

# Sikre .env filen
chmod 600 .env
```

**Test API-nøkler**:
```bash
# Test OpenAI
python3 << 'EOF'
import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

try:
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=10
    )
    print("✅ OpenAI works!")
except Exception as e:
    print(f"❌ OpenAI error: {e}")
EOF

# Test Azure Speech
python3 << 'EOF'
import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv

load_dotenv()

speech_config = speechsdk.SpeechConfig(
    subscription=os.getenv('AZURE_TTS_KEY'),
    region=os.getenv('AZURE_TTS_REGION')
)

try:
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    print("✅ Azure Speech works!")
except Exception as e:
    print(f"❌ Azure error: {e}")
EOF
```

## Del 4: Systemd Services

### 4.1 Opprett service-filer

Sjekk at disse filene finnes:
- `chatgpt-duck.service`
- `duck-control.service`
- `install-services.sh`

### 4.2 Konfigurer sudo-rettigheter

```bash
# Opprett sudoers-fil for duck-control
sudo tee /etc/sudoers.d/duck-control << 'EOF'
admog ALL=(ALL) NOPASSWD: /bin/systemctl start chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /bin/systemctl stop chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /bin/systemctl restart chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /bin/systemctl is-active chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u chatgpt-duck.service*
admog ALL=(ALL) NOPASSWD: /usr/sbin/reboot
admog ALL=(ALL) NOPASSWD: /usr/sbin/shutdown*
EOF

# Verifiser syntax
sudo visudo -c -f /etc/sudoers.d/duck-control
```

### 4.3 Installer services

```bash
cd /home/admog/Code/chatgpt-and

# Gjør install-script executable
chmod +x scripts/install-services.sh

# Kjør installasjon
sudo ./scripts/install-services.sh
```

Dette vil:
1. Kopiere service-filer til `/etc/systemd/system/`
2. Reload systemd daemon
3. Enable services (auto-start ved boot)

### 4.4 Start services

```bash
# Start hovedapplikasjon
sudo systemctl start chatgpt-duck.service

# Start kontrollpanel
sudo systemctl start duck-control.service

# Sjekk status
sudo systemctl status chatgpt-duck.service
sudo systemctl status duck-control.service
```

### 4.5 Verifiser oppstart

```bash
# Sjekk logger for hovedapp
sudo journalctl -u chatgpt-duck.service -f

# Sjekk logger for kontrollpanel
sudo journalctl -u duck-control.service -f

# Du skal se:
# - "Venter på wake word..." (hovedapp)
# - "Serving on port 3000" (kontrollpanel)
```

## Del 5: Test og verifisering

### 5.1 Test wake word

1. RGB LED skal være **blå**
2. Si "**alexa**" eller "**ulrika**" tydelig
3. LED skal bli **grønn**
4. Snakk til anda
5. LED skal blinke **gul** (Azure STT)
6. LED skal blinke **lilla** (ChatGPT tenker)
7. LED skal bli **rød** (anda snakker)
8. Nebb skal bevege seg synkront med tale

### 5.2 Test web-kontrollpanel

1. Finn Pi's IP-adresse:
```bash
hostname -I
```

2. Åpne nettleser på en annen enhet på samme nettverk:
```
http://<pi-ip-adresse>:3000
```

3. Test funksjoner:
   - ✅ Status viser "Duck kjører"
   - ✅ Logger vises med farger
   - ✅ Endre talehastighet og test
   - ✅ Endre volum og test
   - ✅ Send testmelding
   - ✅ Start/stopp service

### 5.3 Test nebb separat

```bash
cd /home/admog/Code/chatgpt-and
python3 duck_beak.py
```

Eller via kontrollpanel: Klikk "Test nebb"

### 5.4 Test alle personligheter

Via kontrollpanel, velg hver personlighet og test respons:

1. **Normal**: "Hei, hvordan går det?"
2. **Entusiastisk**: "Hei, hvordan går det?"
3. **Filosofisk**: "Hva er meningen med livet?"
4. **Humoristisk**: "Fortell meg en vits"
5. **Kort**: "Hva er Python?"

## Del 6: Konfigurasjon og tilpasning

### 6.1 Wake Word

Wake word er nå "Samantha" og bruker Porcupine wake word detection. Wake word er definert av modellen `porcupine/samantha_en_raspberry-pi_v4_0_0.ppn`.

For å endre wake word, må du enten:
1. Lage en custom wake word på https://console.picovoice.ai/
2. Eller bruke en annen forhåndstrent modell fra Picovoice

Sensitivitet kan justeres i `src/duck_speech.py`:
```python
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=[keyword_path],
    sensitivities=[0.5]  # ← 0.0-1.0, høyere = mer sensitiv
)
```

### 6.2 Endre GPIO-pins

Hvis du bruker andre GPIO-pins:

**RGB LED** i `rgb_duck.py`:
```python
def __init__(self, red_pin=17, green_pin=27, blue_pin=22):
```

**Servo** i `duck_beak.py`:
```python
servo = Servo(14)  # ← Endre pin her
```

### 6.3 Justere nebb-følsomhet

I `duck_beak.py`:
```python
def move_beak_with_amplitude(audio_file_path):
    # ...
    amplitude_threshold = 500  # ← Lavere = mer følsomt
    min_angle = 0.0           # ← Min vinkel
    max_angle = 0.5           # ← Max vinkel
```

### 6.4 Endre standard innstillinger

Opprett tmp-filer med standardverdier:
```bash
echo "entusiastic" > /tmp/duck_personality.txt
echo "nb-NO-PernilleNeural" > /tmp/duck_voice.txt
echo "75" > /tmp/duck_volume.txt
echo "on" > /tmp/duck_beak.txt
echo "60" > /tmp/duck_speed.txt
echo "gpt-4-turbo" > /tmp/duck_model.txt
```

### 6.5 Personaliserte hilsener

Anda vil nå bruke navnet ditt i hilsener! Når du første gang forteller Anda hva du heter, lagres navnet i databasen og brukes i fremtidige hilsener.

**Eksempel**:
- Du: "Jeg heter Osmund"
- Anda: "Ok, jeg har lagret at du heter Osmund"
- Neste gang du sier wake word: **"Hei, Osmund. Hva kan jeg hjelpe deg med?"**

**Slik fungerer det**:
1. Fortell Anda navnet ditt: "Jeg heter [navn]"
2. Memory system lagrer `user_name` i databasen
3. Ved neste wake word bruker Anda navnet ditt i hilsenen

**For flere brukere (flere ander)**:
Dette gjør det enkelt å sette opp flere duck-assistenter for forskjellige personer:

```bash
# Lag ny duck-konfigurasjon for en annen person
cd /home/admog/Code/chatgpt-and

# 1. Kopier databasen til backup
cp duck_memory.db duck_memory_backup.db

# 2. Slett eksisterende database (eller start fra scratch)
rm duck_memory.db

# 3. Start anda og si: "Jeg heter [nytt navn]"
# Nå vil denne anda-instansen hilse med det nye navnet!
```

**Meldingskonfigurasjon** i `messages.json`:
```json
{
  "conversation": {
    "greeting": "Hei, {name}. Hva kan jeg hjelpe deg med?"
  },
  "web_interface": {
    "start_conversation": "Hei, {name}. Hva kan jeg hjelpe deg med?"
  }
}
```

Hvis ingen navn er funnet i databasen, faller systemet tilbake til: "Hei, på du. Hva kan jeg hjelpe deg med?"

## Del 7: Autostart ved oppstart

Services er allerede konfigurert for autostart, men verifiser:

```bash
# Sjekk at services er enabled
systemctl is-enabled chatgpt-duck.service
systemctl is-enabled duck-control.service
systemctl is-enabled fan-control.service

# Hvis ikke, enable dem
sudo systemctl enable chatgpt-duck.service
sudo systemctl enable duck-control.service
sudo systemctl enable fan-control.service

# Test reboot
sudo reboot

# Etter reboot, sjekk at alt kjører
sudo systemctl status chatgpt-duck.service
sudo systemctl status duck-control.service
sudo systemctl status fan-control.service
```

## Del 8: Feilsøking

### Problem: Wake word fungerer ikke

**Diagnose**:
```bash
# Test mikrofon
arecord -d 5 -f cd test.wav
aplay test.wav

# Sjekk Porcupine modell
ls -la porcupine/samantha_en_raspberry-pi_v4_0_0.ppn

# Sjekk logger
sudo journalctl -u chatgpt-duck.service -n 50
```

**Løsning**:
- Øk mikrofonvolum: `alsamixer`
- Bruk bedre mikrofon
- Test nærmere til mikrofon
- Snakk tydelig og langsomt

### Problem: Ingen lyd fra høyttaler

**Diagnose**:
```bash
# Test lyd
speaker-test -t wav -c 2

# Sjekk lydkort
aplay -l

# Sjekk Azure TTS
python3 -c "
from azure.cognitiveservices.speech import SpeechSynthesizer, SpeechConfig
import os
from dotenv import load_dotenv
load_dotenv()
config = SpeechConfig(subscription=os.getenv('AZURE_TTS_KEY'), region=os.getenv('AZURE_TTS_REGION'))
synth = SpeechSynthesizer(speech_config=config)
synth.speak_text_async('Test').get()
"
```

**Løsning**:
- Sett riktig audio device i `.asoundrc`
- Øk volum: `alsamixer`
- Sjekk at høyttaler er tilkoblet
- Prøv annen høyttaler (USB eller HDMI)

### Problem: Servo jitterer eller Pi rebooter

**Årsak**: Servo deler strøm med Pi

**Løsning**: 
1. **BRUK SEPARAT STRØMFORSYNING TIL SERVO**
2. Koble VCC til ekstern 5V (ikke Pi's 5V)
3. Koble ground til både Pi og ekstern strøm

### Problem: RGB LED fungerer ikke

**Diagnose**:
```bash
# Test hver farge
python3 -c "from gpiozero import LED; LED(17).on()"  # Rød
python3 -c "from gpiozero import LED; LED(27).on()"  # Grønn
python3 -c "from gpiozero import LED; LED(22).on()"  # Blå
```

**Løsning**:
- Sjekk wiring (riktige GPIO pins)
- Sjekk at ground er koblet
- Sjekk at LED ikke er defekt
- Prøv andre GPIO pins og oppdater kode

### Problem: Web-panel viser "Henter status..."

**Diagnose**:
```bash
# Sjekk at kontrollpanel kjører
sudo systemctl status duck-control.service

# Test endpoint manuelt
curl http://localhost:3000/duck-status
```

**Løsning**:
- Restart kontrollpanel: `sudo systemctl restart duck-control.service`
- Sjekk logger: `sudo journalctl -u duck-control.service -n 50`
- Sjekk at port 3000 ikke er i bruk: `sudo netstat -tulpn | grep 3000`

### Problem: ChatGPT timeout eller feil

**Diagnose**:
```bash
# Test internett
ping -c 4 api.openai.com

# Sjekk API-nøkkel
cat .env | grep OPENAI_API_KEY
```

**Løsning**:
- Verifiser API-nøkkel på https://platform.openai.com/api-keys
- Sjekk at du har credits igjen
- Sjekk internett-forbindelse
- Bruk enklere modell (gpt-3.5-turbo)

### Problem: "Module not found" errors

**Løsning**:
```bash
# Reinstaller dependencies
source .venv/bin/activate
pip install --upgrade -r requirements.txt

# For specific package
pip install --upgrade <package-name>
```

## Del 9: Vedlikehold

### Oppdatere systemet

```bash
cd /home/admog/Code/chatgpt-and

# Oppdater kode
git pull

# Oppdater dependencies
source .venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart services
sudo systemctl restart chatgpt-duck.service
sudo systemctl restart duck-control.service
```

### Rotere logger

```bash
# Sett maks log-størrelse
sudo tee /etc/systemd/journald.conf << 'EOF'
[Journal]
SystemMaxUse=100M
SystemMaxFileSize=10M
EOF

# Restart journald
sudo systemctl restart systemd-journald
```

### Backup konfigurasjon

```bash
# Backup .env og tmp-filer
mkdir -p ~/duck-backup
cp .env ~/duck-backup/
cp /tmp/duck_*.txt ~/duck-backup/
cp /etc/systemd/system/*duck*.service ~/duck-backup/
```

### Monitorere ressursbruk

```bash
# CPU og minne
htop

# Disk space
df -h

# Logger-størrelse
sudo journalctl --disk-usage

# Service ressursbruk
systemctl status chatgpt-duck.service
```

## Del 10: Sikkerhetstips

1. **Aldri commit .env til git**:
```bash
echo ".env" >> .gitignore
```

2. **Begrens nettverkstilgang**:
```bash
# Kun tillat web-panel fra lokalt nettverk
# I duck-control.py: Sjekk client IP
```

3. **Roter API-nøkler regelmessig**:
- OpenAI: Generer ny nøkkel hver måned
- Azure: Bruk Key 2 som backup

4. **Overvåk API-kostnader**:
- OpenAI: https://platform.openai.com/usage
- Azure: https://portal.azure.com (Cost Management)

5. **Oppdater system regelmessig**:
```bash
sudo apt-get update && sudo apt-get upgrade
```

## Ferdig! 🎉

Systemet skal nå være fullt funksjonelt. Test alt grundig før du tar det i daglig bruk.

**Neste steg**:
- Les [ARCHITECTURE.md](ARCHITECTURE.md) for teknisk forståelse
- Les [README.md](../README.md) for brukerveiledning
- Tilpass personligheter og innstillinger etter dine preferanser

**Ved problemer**: Sjekk logger og sammenlign med denne guiden. De fleste problemer skyldes:
1. Feil API-nøkler
2. Audio-konfigurasjon
3. Manglende dependencies
4. Hardware-wiring

**Lykke til med andeprating! 🦆💬**
