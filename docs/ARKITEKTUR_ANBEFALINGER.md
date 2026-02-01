# Duck-Vision + Anda: Arkitektur-beslutninger

## ✅ Anbefalinger for implementasjon

### 1. Arkitektur: DuckVisionService i ServiceManager

**Anbefaling: A + C kombinert**

```python
# I service_manager.py - ny service:
class DuckVisionService(BaseService):
    """Service for MQTT kommunikasjon med Duck-Vision kamera"""
    
    def __init__(self, announce_callback, listen_callback, speak_callback):
        super().__init__()
        self.announce = announce_callback
        self.listen = listen_callback
        self.speak = speak_callback
        self.vision_handler = None
        self.waiting_for_name = False
    
    async def start(self):
        self.vision_handler = DuckVisionHandler(
            broker_host="localhost",
            on_face_detected=self._on_face_detected,
            on_unknown_face=self._on_unknown_face,
            on_object_detected=self._on_object_detected
        )
        if self.vision_handler.connect():
            logger.info("✓ Duck-Vision service started")
        else:
            logger.warning("⚠️ Duck-Vision not available")
    
    async def stop(self):
        if self.vision_handler:
            self.vision_handler.disconnect()
```

**Fordeler:**
- ✅ Konsistent med eksisterende arkitektur
- ✅ Kan startes/stoppes uavhengig
- ✅ Egen lifecycle management
- ✅ Kan disable hvis kamera ikke tilgjengelig

---

### 2. Face Recognition: Announcement (ikke wake word)

**Anbefaling: C) Announcement-systemet**

```python
def _on_unknown_face(self):
    """Ukjent ansikt → direkte announcement (som hunger/boredom)"""
    self.announce("Hei! Jeg ser deg, men jeg vet ikke hvem du er. Hvem er du?")
    self.waiting_for_name = True
    # STT håndteres av main loop - service setter bare flag
```

**Fordeler:**
- ✅ Naturlig interaksjon (ser deg → sier noe med en gang)
- ✅ Konsistent med hunger/boredom announcements
- ✅ Ikke avhengig av wake word
- ✅ Kan avbrytes hvis bruker sier "Samantha" for annen kommando

**Alternativ:** Hvis du vil være mindre "påtrengende", kan første gang være announcement, senere kjente personer bare logges stille.

---

### 3. "Hva ser du?": AI Tool (primary) + Fallback

**Anbefaling: B) AI Tool (med C som backup)**

```python
# I tools.py - nytt AI tool:
{
    "type": "function",
    "function": {
        "name": "look_around",
        "description": "Use the camera to see what objects or people are currently visible in the room. Returns a list of detected objects with Norwegian names.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

# Implementation:
def look_around() -> dict:
    """Request object detection from Duck-Vision"""
    service_manager.vision_service.request_object_detection()
    # Wait for response (med timeout 5s)
    result = service_manager.vision_service.get_last_detection(timeout=5.0)
    return {"objects": result}
```

**Fordeler:**
- ✅ AI bestemmer når den trenger å "se"
- ✅ Kan brukes i kontekst: "Er Magnus her?" → AI kaller look_around() først
- ✅ Mer naturlig enn hardkodede kommandoer

**Fallback:** Behold også direkte kommando "hva ser du" som trigger samme funksjon.

---

### 4. Database: Hybrid (metadata i duck_memory.db)

**Anbefaling: C) Hybrid løsning**

**Pi 5 (Duck-Vision):**
```
/home/admog/Code/Duck-Vision/data/known_faces/{name}/
├── encodings.pkl      # Face encoding vectors (128D numpy array)
└── metadata.json      # Når lagret, confidence threshold, etc
```

**Pi 4 (duck_memory.db):**
```sql
-- Ny tabell:
CREATE TABLE IF NOT EXISTS known_people (
    name TEXT PRIMARY KEY,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    times_seen INTEGER DEFAULT 1,
    notes TEXT  -- "Bor i Oslo", "Magnus sin bror", etc
);

-- Oppdater existing profile_facts:
INSERT INTO profile_facts (fact_type, fact_value) 
VALUES ('known_person', 'Magnus');
```

**Workflow:**
1. Duck-Vision lagrer face encoding (Pi 5)
2. Når person gjenkjennes → MQTT event
3. Anda logger i known_people + profile_facts (Pi 4)
4. Kan senere spørre: "Har du sett Magnus i dag?"

**Fordeler:**
- ✅ Face encodings er for store for database (128D floats × mange bilder)
- ✅ Metadata i database gir Anda "memory" om personer
- ✅ Kan integrere med existing profile system
- ✅ Separation of concerns

---

### 5. Testing: Pi 5 KLAR! ✅

**Status Duck-Vision (Pi 5):**
- ✅ IMX500 SDK installert og testet
- ✅ Object detection: 0.6ms latency, perfekt norske navn
- ✅ Face detection: Fungerer med PoseNet
- ✅ dlib + face_recognition: **FERDIG INSTALLERT** (exit code 0!)
- ✅ MQTT client klar
- ✅ All kode skrevet og klar

**Neste steg:**
1. **Test face recognition** (5 min):
   ```bash
   # På Pi 5
   cd /home/admog/Code/Duck-Vision
   python3 -c "import face_recognition; print('✓ face_recognition works!')"
   python3 demo_face_recognition.py  # Lag denne testen
   ```

2. **Start Duck-Vision system** (1 min):
   ```bash
   python3 duck_vision.py
   ```

3. **Implementer på Pi 4** (30-60 min):
   - Installer MQTT broker
   - Kopier duck_vision_integration.py
   - Lag DuckVisionService
   - Legg til AI tool
   - Test!

---

### 6. Scope: Pilot først (object detection), deretter full

**Anbefaling: B → A) Object detection først, så face recognition**

**FASE 1 (pilot, 30 min implementasjon):**
```python
✓ Object detection only
✓ AI tool: look_around()
✓ Kommando: "Hva ser du?"
✓ DuckVisionService (basic)
✓ MQTT kommunikasjon
```

**Fordeler:**
- ✅ Raskeste veien til working demo
- ✅ Ingen privacy concerns (ingen ansiktsdata)
- ✅ Tester full MQTT stack
- ✅ Kan vise resultat med én gang (0.6ms deteksjon!)
- ✅ Mindre kompleks workflow

**FASE 2 (full, +30 min):**
```python
✓ Face recognition
✓ Unknown face announcements
✓ Learning workflow med samtykke
✓ Database integration (known_people)
✓ Greetings ved kjent ansikt
```

**Hvorfor ikke face først?**
- ⚠️ Mer kompleks (announcements, STT workflow, database)
- ⚠️ Krever testing med reelle personer
- ⚠️ Privacy considerations (GDPR, samtykke)
- ⚠️ Flere edge cases (hva hvis name extraction feiler?)

**Konkret plan:**

**PILOT (i dag):**
1. Lag minimal DuckVisionService (kun object detection)
2. Lag look_around() AI tool
3. Test: "Samantha, hva ser du?" → "Jeg ser en laptop"
4. ✅ SUCCESS! System fungerer!

**FULL (når pilot virker):**
5. Utvid DuckVisionService med face callbacks
6. Legg til announcement system
7. Legg til database tabell
8. Test full face learning workflow
9. ✅ COMPLETE! Full vision system!

---

**FASE 2+ (framtidig utvidelser):**
- [ ] "Jeg har ikke sett Magnus på 3 dager" (query known_people)
- [ ] Memory integration: "Sist jeg så deg hadde du briller"
- [ ] Confidence-based greetings: høy confidence → "Hei Magnus!", lav → "Er du Magnus?"
- [ ] Multi-face detection: "Jeg ser både Magnus og Maria"
- [ ] Object memory: "Du spurte om laptop for 10 min siden, den er fortsatt der"
- [ ] Spatial memory: "Laptopen er på bordet til venstre"
- [ ] Change detection: "Noen har flyttet koppen"

---

## 📁 Filer du trenger å endre (Pi 4):

### FASE 1 (Pilot - Object Detection):

1. **duck_vision_integration.py** (kopier fra Pi 5)
   - `scp duck_vision_integration.py admog@oDuckberry-2.local:~/chatgpt-and/`

2. **service_manager.py**
   - Legg til `DuckVisionService` class (minimal version)
   - Import `DuckVisionHandler`

3. **main.py**
   - Initialize vision service: `vision_service = DuckVisionService(...)`
   - Start service i service_manager

4. **tools.py** (eller der du har AI tools)
   - Legg til `look_around()` function
   - Legg til i tools array for OpenAI

### FASE 2 (Full - Face Recognition):

5. **service_manager.py** (utvid)
   - Legg til face detection callbacks
   - Legg til announcement system

6. **duck_memory.db** (SQL migration)
   - Kjør CREATE TABLE for `known_people`

7. **main.py** (utvid)
   - Legg til database logging for face events

---

## 🚀 Installasjon Pi 4 (5 minutter):

```bash
ssh admog@oDuckberry-2.local

# 1. MQTT Broker
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# 2. Python dependencies
cd ~/chatgpt-and
pip3 install paho-mqtt

# 3. Test MQTT
mosquitto_sub -t "duck/#" -v &
# La stå åpen i bakgrunnen for testing

# 4. Database migration
sqlite3 duck_memory.db << EOF
CREATE TABLE IF NOT EXISTS known_people (
    name TEXT PRIMARY KEY,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMPintegrasjon:

### FASE 1 (Pilot - Object Detection):

| Oppgave | Tid | Status |
|---------|-----|--------|
| Installer MQTT broker (Pi 4) | 5 min | Må gjøres |
| Kopier integrasjonsfil | 1 min | Må gjøres |
| Lag minimal DuckVisionService | 10 min | Må kodes |
| Legg til AI tool: look_around() | 10 min | Må kodes |
| Testing + debugging | 10 min | Må gjøres |
| **PILOT TOTALT** | **~35 min** | ✅ **Test system!** |

### FASE 2 (Full - Face Recognition):

| Oppgave | Tid | Status |
|---------|-----|--------|
| Utvid DuckVisionService (callbacks) | 15 min | Må kodes |
| Legg til announcement system | 5 min | Må kodes |
| Database migration (known_people) | 2 min | Må kjøres |
| Testing face learning workflow | 20 min | Må gjøres |
| **FULL TOTALT** | **+40 min** | |

### **TOTAL TID: ~1 time 15 min** (men 35 min til working demo!)tegrasjon:

| Oppgave | Tid | Status |
|---------|-----|--------|
| Test face recognition (Pi 5) | 5 min | Klar nå |
| Installer MQTT broker (Pi 4) | 5 min | Må gjøres |
| Kopier integrasjonsfil | 1 min | Må gjøres |
| Lag DuckVisionService | 15 min | Må kodes |
| Legg til AI tool | 10 min | Må kodes |
| Database migration | 2 min | Må kjøres |
| Testing + debugging | 30 min | Må gjøres |
| **TOTALT** | **~1 time** | |

---

## ✅ Oppsummering

**Implementasjonsplan:**
1. ✅ Test face recognition på Pi 5 **FØRST** (sikre at alt fungerer)
2. Installer MQTT broker på Pi 4
3. Lag DuckVisionService i service_manager.py
4. Lag AI tool look_around() i tools.py
5. Kjør database migration
6. Start begge systemer og test!

**Arkitektur-valg:**
- Service-based (ikke direkte i main.py)
- Announcement for ansiktsgjenkjenning (ikke wake word)
- AI tool for "se rundt deg" (AI bestemmer)
- Hybrid database (encodings på Pi 5, metadata på Pi 4)

**Status:** 
- Pi 5: ✅ KLAR
- Pi 4: 🔨 Trenger 1 time implementasjon

---

**Neste steg: Test face_recognition på Pi 5, så er vi klare til full integrasjon! 🦆⚡**
