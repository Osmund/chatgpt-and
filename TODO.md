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

### Kodebase
- [ ] Dokumentere PYTHONPATH-kravet i README/INSTALL.md
- [ ] Vurder dynamisk BASE_PATH i service-filer
- [ ] Lag backup/restore-funksjonalitet for database
- [ ] Legg til mer omfattende error handling

### Testing
- [ ] Lag enhetstester for moduler i src/
- [ ] Integrasjonstester for AI tools
- [ ] Test memory system under load

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
