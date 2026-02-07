# 🦆 ChatGPT Duck - TODO & Future Features

## 📅 Planlagt for våren 2025

### 🎥 Vision/Kamera-integrasjon

#### Hardware
- [ ] Skaffe **Raspberry Pi Camera Module 3** (eller USB-webkamera)
- [ ] Montere kamera på anda (best plassering?)
- [ ] Teste kameravinkel og fokus

#### Funksjonalitet

##### 1. Grunnleggende bildeanalyse
- [ ] Implementere `src/duck_vision.py` modul
- [ ] Integrere OpenAI GPT-4 Vision API
- [ ] Støtte for:
  - Objektgjenkjenning ("Hva ser du?")
  - Sceneforståelse ("Beskriv rommet")
  - Tekstgjenkjenning (OCR)
  - Fargegenkjenning

##### 2. Ansiktsgjenkjenning
- [ ] Installere `face_recognition` library
- [ ] Lagre kjente ansikter i database
- [ ] Gjenkjenne brukere visuelt
- [ ] Integrere med eksisterende user manager
- [ ] Personalisert hilsen basert på ansikt

##### 3. QR/strekkode-skanning
- [ ] Implementere `pyzbar` eller `opencv`
- [ ] Skanne QR-koder
- [ ] Lese strekkoder (produkt-lookup?)
- [ ] Lagre WiFi-passord via QR

##### 4. Bevegelse og gester
- [ ] Detektere bevegelse med OpenCV
- [ ] Gjenkjenne håndbevegelser
- [ ] Vinke for å vekke anda (alternativ til wake word)
- [ ] Peke på objekter ("Hva er det der?")

##### 5. Proaktiv oppførsel
- [ ] Anda ser deg komme inn → hilser proaktivt
- [ ] Detektere når du ser frustrert ut → spør om hjelp
- [ ] Legger merke til nye gjenstander i rommet
- [ ] Reminder når du går forbi: "Du skulle ta med nøklene!"

##### 6. Visuelt minne
- [ ] Lagre snapshots med timestamp
- [ ] "Hvor la jeg nøklene?" → søk i bildeminne
- [ ] "Når så du katten sist?" → finn tidsstempel
- [ ] Integrere med eksisterende memory system

#### Tekniske detaljer
- [ ] Vurdere CPU-belastning (Pi kan bli treg med Vision API)
- [ ] Cache bilder lokalt før sending til API
- [ ] Komprimere bilder for raskere opplasting
- [ ] Implementere rate limiting (Vision API er dyrere)
- [ ] Lag konfigurasjon for når kamera skal være aktivt
- [ ] Privacy: Lag indikator når kamera er på

#### Potensielle utfordringer
- [ ] **Performance**: Bildeanalyse kan være treg på Pi
- [ ] **Kostnad**: GPT-4 Vision er dyrere enn standard GPT
- [ ] **Privacy**: Kamera krever tillit fra brukere
- [ ] **Lighting**: Dårlig lys kan gi dårlige resultater
- [ ] **Montering**: Hvor på anda skal kameraet sitte?

---

## 🔧 Andre forbedringer

### Arkitektur (høy prioritet)
- [x] **Event-bus/Queue**: Erstatt ~15 `/tmp/duck_*.txt`-filer med `queue.Queue` — fjerner race conditions, ~150 linjer duplikat, og polling-overhead *(commit 4e05b87, 7. feb 2026)*
- [ ] **ConversationStateMachine**: Trekk ut ~800 linjer fra `main()` i chatgpt_voice.py til en tilstandsmaskin (IDLE → WAKE → LISTENING → PROCESSING → SPEAKING)
- [x] **Sentralisert DB**: Lag `DatabaseManager` med connection pool og context managers i ServiceManager — fjerner 30+ spredte `sqlite3.connect()`-kall *(commit b0a3a30, feb 2026)*
- [x] **DuckSettings-klasse**: Samle all config-lesing (beak, volume, sleep, etc.) — fjerner 3x duplisert beak/volum-lesemønster *(commit 25a1be3, feb 2026)*

### Kodebase (middels prioritet)
- [x] Fjern 13+ hardkodede `/home/admog/Code/chatgpt-and/`-stier — bruk `BASE_PATH`/`DB_PATH` fra duck_config.py *(commit pending, 7. feb 2026)*
- [x] Fiks 9x `sys.path.insert`-hacks — én `sys.path` per entry point, fiks pakkestruktur *(commit pending, 7. feb 2026)*
- [ ] Splitt `duck_ai.py` (2074 linjer) — flytt tool-definisjoner til `duck_tool_definitions.py`, bryt opp `_build_system_prompt()`
- [ ] Splitt `duck-control.py` (1925 linjer) — flytt inline SQL til DuckAPIHandlers, vurder Flask
- [ ] Fiks requirements.txt — `audioop-lts` er klebet til `requests`-kommentaren, mangler `paho-mqtt`, `twilio`
- [ ] Dokumentere PYTHONPATH-kravet i README/INSTALL.md
- [x] Vurder dynamisk BASE_PATH i service-filer *(løst: alle stier bruker nå BASE_PATH/DB_PATH/MUSIKK_DIR fra duck_config.py)*
- [ ] Legg til mer omfattende error handling

### Sikkerhet
- [ ] Legg til auth på kontrollpanelet (port 3000) — ingen autentisering i dag
- [ ] Beskytt SMS-autorisasjon mot endring via kontrollpanelet
- [ ] Fjern `str(e)` fra JSON-svar — eksponerer filstier og stack traces

### Testing
- [ ] Lag enhetstester for `duck_memory.py` (MemoryManager, embedding-søk)
- [ ] Lag enhetstester for `duck_ai.py` (chatgpt_query, metadata, duration parsing)
- [ ] Lag enhetstester for `duck_messenger.py` (loop detection, token budgets)
- [ ] Integrasjonstester for AI tools
- [ ] Test memory system under load

### Ytelse
- [ ] Cach pitch-shifted audio for gjentatte fraser (oppstartshilsen, feilmeldinger)
- [x] Per-tråd persistent SQLite-connection i stedet for åpne/lukke per kall *(DatabaseManager med thread-local connections)*
- [ ] Trådsikring av globaler (`_waiting_for_name` etc.) med `threading.Lock`

### Deployment
- [ ] Lag installer-script for nye systemer
- [ ] Automatiser service-setup
- [ ] Dokumentere troubleshooting (f.eks. ModuleNotFoundError)

### Features
- [ ] Flere musikk-kilder (Spotify? YouTube Music?)
- [ ] Kalender-integrasjon ("Hva har jeg i morgen?")
- [ ] Smart home: flere enheter (termostat, lås, etc.)
- [ ] Multi-bruker: skill mellom ulike stemmer

---

## 📝 Notater
- Crash 2026-01-15: Pi rebooted pga memory worker crash-loop
  - Løsning: PYTHONPATH i service-filer + import fix
  - Watchdog timeout på 60 sekunder trigget reboot
- Desktop GUI (lightdm) bruker ~14 MB, vurder å disable
