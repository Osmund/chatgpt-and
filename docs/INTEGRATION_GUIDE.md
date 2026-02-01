# Duck-Vision + Anda Integrasjon: Setup Guide

## 🎯 Oversikt

Dette dokumentet beskriver **nøyaktig** hvordan du integrerer Duck-Vision (Pi 5) med Anda/Samantha (Pi 4).

**Alle steg er copy-paste klare!** Ingen gjetning, bare følg instruksjonene.

### Hva oppnår vi?

1. **Ansiktsgjenkjenning med samtykke-workflow:**
   - Ukjent person → Anda spør "Hvem er du?"
   - Får navn → "Får jeg lov å huske deg?"
   - Hvis ja → Lagrer ansikt med navn
   - Neste gang → "Hei [navn]!" direkte!

2. **Object detection på kommando:**
   - "Hva ser du?" → Anda forteller hva Duck-Vision ser
   - 0.6ms latency fra IMX500 AI-chip!

3. **MQTT kommunikasjon:**
   - Real-time events mellom Pi 5 og Pi 4
   - Kjører i bakgrunnen, stører ikke existing funksjonalitet

## 📋 Arkitektur

```
┌─────────────────────┐          MQTT           ┌─────────────────────┐
│   Pi 5 (Vision)     │ ◄──────────────────────► │   Pi 4 (Anda)       │
│  oDuckberry-vision  │                          │  oDuckberry-2       │
├─────────────────────┤                          ├─────────────────────┤
│ • IMX500 AI Camera  │                          │ • MQTT Broker       │
│ • Object Detection  │  Events: face, object    │ • chatgpt_voice.py  │
│ • Face Recognition  │  ─────────────────────►  │ • TTS/STT           │
│ • 0.6ms latency ⚡   │                          │ • OpenAI API        │
│                     │  Commands: learn, detect │                     │
│                     │  ◄─────────────────────  │                     │
└─────────────────────┘                          └─────────────────────┘
```

## 🚀 Setup: Pi 4 (Anda/Samantha)

### 1. Installer MQTT Broker

```bash
# SSH til Pi 4
ssh admog@oDuckberry-2.local

# Installer mosquitto
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients

# Enable og start service
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Verifiser at det kjører
sudo systemctl status mosquitto

# Test med subscriber (i ett terminal vindu)
mosquitto_sub -t "duck/#" -v
```

### 2. Kopier integrasjonsfil

```bash
# På Pi 5, kopier til Pi 4:
scp /home/admog/Code/Duck-Vision/duck_vision_integration.py admog@oDuckberry-2.local:~/chatgpt-and/
```

### 3. Installer Python dependencies på Pi 4

```bash
# På Pi 4
cd ~/chatgpt-and
pip3 install paho-mqtt
```

### 4. Integrer i chatgpt_voice.py

**VIKTIG:** Dette er KOMPLETT kode klar for copy-paste!

#### Steg 4.1: Legg til imports i toppen av filen

```python
# Finn linjen med dine andre imports, legg til disse:
from duck_vision_integration import DuckVisionHandler
import re
```

#### Steg 4.2: Legg til hjelpefunksjoner (før main())

```python
# ═══════════════════════════════════════════════════════════
# DUCK-VISION HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def extract_name_from_text(text):
    """
    Ekstraher navn fra bruker-respons.
    Eksempel: "jeg heter Magnus" → "Magnus"
    """
    text = text.lower()
    
    # Patterns for navn
    patterns = [
        r"jeg heter (\w+)",
        r"jeg er (\w+)", 
        r"mitt navn er (\w+)",
        r"navnet mitt er (\w+)",
        r"kaller meg (\w+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1)
            return name.capitalize()
    
    # Hvis ingen pattern matcher, bruk første ord >3 bokstaver
    words = text.split()
    for word in words:
        word = word.strip('.,!?')
        if len(word) > 3 and word.isalpha():
            return word.capitalize()
    
    return None

def is_affirmative(text):
    """Sjekk om respons er bekreftende"""
    text = text.lower()
    yes_words = ['ja', 'yes', 'ok', 'greit', 'gjerne', 'sure', 'yep', 'jepp', 'sikkert']
    return any(word in text for word in yes_words)
```

#### Steg 4.3: Legg til Duck-Vision setup i main()

**FINN denne linjen i din main():**
```python
def main():
    # Her er ditt existing setup...
```

**LEGG TIL rett etter andre initialiseringer (før while-løkken):**

```python
    # ═══════════════════════════════════════════════════════════
    # DUCK-VISION INTEGRATION SETUP
    # ═══════════════════════════════════════════════════════════
    
    # Global variabel for å holde styr på pending person
    pending_person_name = [None]  # List for closure
    
    def on_face_detected(name, confidence):
        """Callback når kjent ansikt detekteres"""
        import datetime
        hour = datetime.datetime.now().hour
        
        if hour < 10:
            greeting = "God morgen"
        elif hour < 18:
            greeting = "Hei"
        else:
            greeting = "God kveld"
        
        speak(f"{greeting} {name}!")
        print(f"👋 Hilste på {name} (confidence: {confidence:.2%})")
    
    def on_unknown_face():
        """Callback når ukjent ansikt detekteres"""
        speak("Hei! Jeg ser deg, men jeg vet ikke hvem du er. Hvem er du?")
        
        # Lytt etter navn
        response = listen()  # Bruk din existing listen() funksjon
        if response:
            name = extract_name_from_text(response)
            if name:
                # Spør om lov til å huske
                speak(f"Hei {name}! Får jeg lov å huske deg?")
                confirm = listen()
                
                if confirm and is_affirmative(confirm):
                    # Send kommando til Duck-Vision
                    vision.learn_person(name)
                    pending_person_name[0] = name
                    
                    speak("Supert! Se mot kameraet på veggen...")
                    time.sleep(3)  # Gi tid til å ta bilde
                    speak(f"Takk {name}! Nå kjenner jeg deg!")
                    
                    pending_person_name[0] = None
                else:
                    speak("Ok, jeg husker deg ikke da.")
            else:
                speak("Beklager, jeg hørte ikke navnet ditt.")
    
    def on_object_detected(obj_name, confidence):
        """Callback når objekt detekteres"""
        speak(f"Jeg ser en {obj_name}")
        print(f"👁️ Detektert: {obj_name} (confidence: {confidence:.2%})")
    
    # Initialize Duck-Vision handler
    print("\n🦆 Connecting to Duck-Vision...")
    vision = DuckVisionHandler(
        broker_host="localhost",  # MQTT broker på samme maskin
        on_face_detected=on_face_detected,
        on_unknown_face=on_unknown_face,
        on_object_detected=on_object_detected
    )
    
    if vision.connect():
        print("✓ Duck-Vision integrasjon aktiv!")
    else:
        print("⚠️ Duck-Vision ikke tilgjengelig (kjører den på Pi 5?)")
    
    # ═══════════════════════════════════════════════════════════
    # END DUCK-VISION SETUP
    # ═══════════════════════════════════════════════════════════
```

#### Steg 4.4: Legg til kommandohåndtering i din conversation loop

**FINN der du håndterer bruker-input (vanligvis inne i while-løkken):**

```python
# Der du har noe som:
# user_input = listen()
# if "vær" in user_input:
#     # handle weather
```

**LEGG TIL disse Duck-Vision kommandoene:**

```python
    # ═══════════════════════════════════════════════════════════
    # DUCK-VISION COMMANDS
    # ═══════════════════════════════════════════════════════════
    
    # "Hva ser du?" - Object detection
    if any(phrase in user_input.lower() for phrase in ["hva ser du", "hva kan du se", "se etter"]):
        speak("La meg se...")
        vision.request_object_detection()
        continue  # Gå til neste loop iteration
    
    # "Hvem kjenner du?" - List known people
    if any(phrase in user_input.lower() for phrase in ["hvem kjenner du", "hvem kan du", "kjenner du noen"]):
        speak("La meg tenke...")
        vision.list_known_people()
        # Du kan også legge til en callback i DuckVisionHandler for å få listen tilbake
        continue
    
    # "Glem [navn]" - Forget person
    if "glem" in user_input.lower():
        name_to_forget = extract_name_from_text(user_input)
        if name_to_forget:
            vision.forget_person(name_to_forget)
            speak(f"Ok, jeg har glemt {name_to_forget}")
        else:
            speak("Hvem skal jeg glemme?")
        continue
    
    # ═══════════════════════════════════════════════════════════
    # ... resten av dine existing commands ...
    # ═══════════════════════════════════════════════════════════
```

#### Steg 4.5: Cleanup ved exit

**FINN der du cleaner up (vanligvis nederst i main() eller i finally block):**

```python
    # Legg til før exit:
    print("\n🛑 Kobler fra Duck-Vision...")
    vision.disconnect()
```

## 🚀 Setup: Pi 5 (Duck-Vision)

Alt er allerede konfigurert! Bare start systemet:

```bash
# SSH til Pi 5
ssh admog@oDuckberry-vision.local

cd ~/Code/Duck-Vision

# Start Duck-Vision
python3 duck_vision.py
```

## 🧪 Testing

### Test 1: MQTT Kommunikasjon

**Terminal 1 (Pi 4):**
```bash
mosquitto_sub -t "duck/#" -v
```

**Terminal 2 (Pi 5):**
```bash
cd ~/Code/Duck-Vision
python3 -c "
import paho.mqtt.client as mqtt
import json
client = mqtt.Client()
client.connect('oDuckberry-2.local', 1883)
client.publish('duck/vision/face', json.dumps({'person_name': 'Test', 'is_known': True}))
print('✓ Sent test message')
"
```

Du skal se meldingen i Terminal 1!

### Test 2: Full Workflow - Ukjent Person

1. Start Anda på Pi 4: `python3 chatgpt_voice.py`
2. Start Duck-Vision på Pi 5: `python3 duck_vision.py`
3. Gå foran kamera på Pi 5
4. **Forventet:**
   - Anda: "Hei! Hvem er du?"
   - Du: "Jeg heter Magnus"
   - Anda: "Hei Magnus! Får jeg lov å huske deg?"
   - Du: "Ja"
   - Anda: "Supert! Se mot kameraet..."
   - [2 sekunder pause]
   - Anda: "Takk! Nå kjenner jeg deg, Magnus!"

### Test 3: Full Workflow - Kjent Person

1. Gå foran kamera igjen
2. **Forventet:**
   - Anda: "Hei Magnus!" (med en gang!)

### Test 4: Object Detection

1. Si til Anda: "Hva ser du foran deg?"
2. **Forventet:**
   - Anda: "La meg se..."
   - [Duck-Vision detekterer objekt på 0.6ms!]
   - Anda: "Jeg ser en laptop" (eller hva enn som er der)

## 📊 MQTT Topics

### Events fra Duck-Vision → Anda

| Topic | Payload | Beskrivelse |
|-------|---------|-------------|
| `duck/vision/face` | `{"person_name": "Magnus", "is_known": true, "confidence": 0.87}` | Ansikt detektert |
| `duck/vision/object` | `{"object_name": "kopp", "confidence": 0.92}` | Objekt detektert |
| `duck/vision/event` | `{"type": "person_learned", "name": "Magnus", "success": true}` | Generisk event |

### Commands fra Anda → Duck-Vision

| Topic | Payload | Beskrivelse |
|-------|---------|-------------|
| `duck/samantha/commands` | `{"command": "detect_object"}` | Be om object detection |
| `duck/samantha/commands` | `{"command": "learn_person", "name": "Magnus"}` | Lær ny person |
| `duck/samantha/commands` | `{"command": "forget_person", "name": "Magnus"}` | Glem person |
| `duck/samantha/commands` | `{"command": "list_people"}` | List kjente personer |

## 🎯 Eksempel: Komplett Workflow

```
┌────────────────────────────────────────────────────────────┐
│ SCENARIO: Ukjent person kommer inn i rommet               │
└────────────────────────────────────────────────────────────┘

1. [Pi 5] IMX500 detekterer ansikt → "ukjent" (10ms)
   ├─ duck_vision.py: face_recognizer.detect_faces()
   └─ Sender MQTT: duck/vision/face
      {"person_name": "ukjent", "is_known": false}

2. [Pi 4] Anda mottar event via MQTT callback
   ├─ on_unknown_face() kalles
   └─ TTS: "Hei! Jeg ser deg, men jeg vet ikke hvem du er. Hvem er du?"

3. [Person] "Jeg heter Magnus"
   ├─ STT på Pi 4: tekst = "jeg heter magnus"
   └─ extract_name(): "Magnus"

4. [Pi 4] Anda spør om samtykke
   └─ TTS: "Hei Magnus! Får jeg lov å huske deg?"

5. [Person] "Ja"
   ├─ STT: "ja"
   └─ Sender MQTT: duck/samantha/commands
      {"command": "learn_person", "name": "Magnus"}

6. [Pi 5] Duck-Vision mottar kommando
   ├─ Tar bilde med IMX500
   ├─ face_recognizer.add_person("Magnus", image)
   ├─ Lagrer encoding til disk
   └─ Sender MQTT: duck/vision/event
      {"type": "person_learned", "name": "Magnus", "success": true}

7. [Pi 4] Anda bekrefter
   └─ TTS: "Takk! Nå kjenner jeg deg, Magnus!"

┌────────────────────────────────────────────────────────────┐
│ SCENARIO: Magnus kommer tilbake senere                    │
└────────────────────────────────────────────────────────────┘

1. [Pi 5] IMX500 detekterer ansikt → "Magnus" (15ms!)
   └─ Sender MQTT: duck/vision/face
      {"person_name": "Magnus", "is_known": true, "confidence": 0.87}

2. [Pi 4] Anda hilser direkte
   └─ TTS: "Hei Magnus!" 👋
```

## 🐛 Troubleshooting

### Problem: "Connection refused" på MQTT

**Løsning:**
```bash
# På Pi 4
sudo systemctl status mosquitto
sudo systemctl restart mosquitto

# Sjekk at den lytter:
sudo netstat -tulpn | grep 1883
```

### Problem: Duck-Vision får ikke kontakt med broker

**Løsning:**
```bash
# På Pi 5, test MQTT connection:
mosquitto_pub -h oDuckberry-2.local -t "test" -m "hello"

# Hvis det feiler, sjekk .env fil:
cat /home/admog/Code/Duck-Vision/.env
# Skal inneholde: MQTT_BROKER=oDuckberry-2.local
```

### Problem: Callbacks kalles ikke

**Debug:**
```python
# I duck_vision_integration.py, legg til debug logging:
def _on_message(self, client, userdata, msg):
    print(f"DEBUG: Received {msg.topic}: {msg.payload}")
    # ... rest of code
```

### Problem: Face recognition er treg

**Forventet:**
- Første deteksjon: ~4000ms (laster firmware)
- Påfølgende: ~10-30ms

Hvis tregere, sjekk:
```bash
# På Pi 5
htop  # Sjekk CPU/RAM bruk
```

## ✅ Sjekkliste før produksjon

- [ ] MQTT broker kjører på Pi 4
- [ ] Duck-Vision starter uten feil på Pi 5
- [ ] MQTT kommunikasjon fungerer begge veier
- [ ] Face detection fungerer (test med ukjent person)
- [ ] Face learning fungerer (test full workflow)
- [ ] Face recognition fungerer (test kjent person)
- [ ] Object detection fungerer ("hva ser du?")
- [ ] Anda integrering komplett i chatgpt_voice.py
- [ ] Systemd services satt opp (optional)

## 🚀 Autostart (Optional)

Lag systemd service for autostart:

**På Pi 5** - `/etc/systemd/system/duck-vision.service`:
```ini
[Unit]
Description=Duck-Vision AI Camera System
After=network.target

[Service]
Type=simple
User=admog
WorkingDirectory=/home/admog/Code/Duck-Vision
ExecStart=/usr/bin/python3 /home/admog/Code/Duck-Vision/duck_vision.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable duck-vision
sudo systemctl start duck-vision
```

---

**Status: Klar til testing når face_recognition er ferdig installert! 🦆⚡**
