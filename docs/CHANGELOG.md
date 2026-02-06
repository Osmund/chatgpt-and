# Changelog

Alle viktige endringer i ChatGPT Duck-prosjektet dokumenteres her.

Formatet er basert på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.3.0] - 2026-02-06

### Ytelse & Infrastruktur

#### 🔧 Auto-Hotspot Redesign
- Separert WiFi-portal og WiFi-watchdog i egne services
- Portal kjører kun ved behov, watchdog overvåker kontinuerlig
- Bedre stabilitet og ressursbruk

#### ⚡ Kontrollpanel Performance
- Byttet til `ThreadingHTTPServer` for parallelle requests
- Batch polling: én `/dashboard-status` erstatter 6 separate kall
- Template caching: HTML/CSS/JS lastes fra disk én gang

#### 🔄 Shutdown/Reboot UX
- Umiddelbar HTTP-respons før systemkommando kjøres
- Visuell progress bar med steg-indikator
- Forhindrer timeout-feil i nettleseren

#### 🎤 Samtalerespons: 4 Sekunder Raskere
- Fjernet unødvendig `get_boredom()` kall fra samtaleflyt
- Redusert silence-deteksjon fra 1.5s → 1.0s
- Streamet Azure STT med 0.3s pre-buffer

### Memory & Intelligens

#### 🧠 Memory Worker v2 (11 forbedringer)
- Topic-normalisering: "ChatGPT → AI" dedup
- 6 nye database-indekser for raskere oppslag
- Fikset embedding-duplikater (sjekker hash før insert)
- Bedre session-håndtering med mood/theme
- Smart batch-prosessering med backoff

#### 💰 Token-Optimalisering (~3000-5000 spart per tur)
- Fjernet fullt JSON-personlighets-objekt fra system prompt
- Komprimert personlighets-instruksjon til 2 linjer
- Kuttet fakta til maks 2 linjer + relevans-poeng
- Minner begrenset til 1 linje + score
- Fjernet verbose embedding-diagnostikk fra prompt
- Samlet instruksjoner under felles header

#### 🦆 Smartere And (4 intelligens-forbedringer)
- **Session-kontinuitet**: `get_last_session_summary()` gir Anda kontekst fra forrige samtale
- **Multi-message minnessøk**: Søker med siste 3 meldinger (ikke bare siste)
- **Ekte similarity scores**: Bruker cosine similarity i stedet for hardkodet 1.0
- **API retry-logikk**: 3 forsøk med eksponentiell backoff på 429/500/502/503

### Kontrollpanel

#### 🎨 Full Redesign av Kontrollpanel
- **7 logiske seksjoner** i stedet for 10+ uorganiserte
- **Dashboard**: Kompakt 2×3 grid (bruker, HA, lokasjon, vision, CPU, RAM)
- **Tamagotchi**: Sult, kjedsomhet og søvn samlet
- **Snakk med Anda**: Samtale + meldinger + musikk i én seksjon
- **SMS**: Tab-switching mellom historikk og kontakter
- **Innstillinger**: Stemme/lyd og AI/oppførsel i grupperte underkategorier
- **System**: Tjenester, brukere, logger, 3D-printer, vifte, backup, WiFi, faresone
- Fjernet alle inline-stiler → CSS-klasser
- Responsive grid-baserte knappgrupper
- `<details>` element for minneinnstillinger

#### 📱 SMS-Forbedringer
- Kompakt dropdown-filter erstatter pill-knapper
- Viser navn på alle meldinger: "Fra Osmund", "Til Osmund"
- Duck-meldinger viser avsender: "🦆 Fra Samantha"
- Laster alle meldinger direkte (ikke tom side)

## [2.2.1] - 2026-01-28

### Forbedringer

#### 🎯 Relevance Boosting for Personaliserte Minner

**Beskrivelse**: Anda gir nå mer personaliserte svar ved å prioritere minner om personen hun snakker med, samtidig som hun har tilgang til alle sine minner.

**Funksjonalitet**:
- **Semantisk søk i alle minner**: Alle minner søkes for best mulig kontekst
- **+0.15 boost** til minner hvor `user_name` matcher personen i samtalen
- **Balansert prioritering**: Personlige minner kommer først, men relevante minner om andre personer inkluderes også
- **Eksempel**: Når Arvid spør om kamskjell:
  - Arvid-minner (0.75 → 0.90) rangeres høyere
  - Osmund-minner (0.70 → 0.70) inkluderes hvis relevante
  - Gir både personlig og bredere kontekst

**Teknisk implementering**:
- `search_memories_by_embedding()`: Ny `boost_user` parameter
- `build_context_for_ai()`: Sender `user_name` som `boost_user`
- Boost adderes til similarity score før sortering
- Justerbar boosting-verdi (default: 0.15)

**Filer endret**:
- `src/duck_memory.py`: Implementert relevance boosting
- `docs/MEMORY_SYSTEM.md`: Dokumentert algoritme og eksempler

## [2.2.0] - 2026-01-25

### Ny funksjonalitet

#### 💤 Sleep Mode - Forhindre falske wake words

**Beskrivelse**: Anda kan nå settes i "sleep mode" for å forhindre falske aktivering under filmer eller når du trenger ro.

**Funksjoner**:
- **Blå LED-pulsering**: Sinusformet pulsing (0.1-1.0 intensity, 2s syklus) indikerer sleep mode
- **Wake word blokkering**: Anda reagerer ikke på "Samantha" mens den sover
- **Tre aktiveringsmåter**:
  1. **Stemme**: Si "sov i 30 minutter", "sov i 2 timer", "sov i 90 minutter"
  2. **SMS**: Send "våkn opp" eller "wake up" for å deaktivere
  3. **Kontrollpanel**: Web UI med countdown timer og toggle-knapp
- **Norsk varighetsparser**: Forstår "timer", "minutter", "1.5 timer", etc.
- **Auto-deaktivering**: Våkner automatisk når tiden er ute
- **Cross-process sync**: JSON-basert state (sleep_mode.json) synkroniseres mellom alle prosesser
- **AI-awareness**: ChatGPT vet når den sover og svarer ærlig ("Ja, jeg sover til kl 15:30")
- **Umiddelbar aktivering**: [AVSLUTT] marker tvinger samtale-terminering

**Teknisk implementering**:
- **SleepModeManager** (`src/duck_sleep.py`): Singleton med JSON persistence
  - `enable_sleep(duration_minutes)`: Aktiverer med timestamp
  - `disable_sleep()`: Deaktiverer og sletter state
  - `is_sleeping()`: Re-loader JSON hver gang (cross-process sync)
  - `get_sleep_status()`: Returnerer detaljert status med countdown
- **LED kontroll** (`rgb_duck.py`):
  - `pulse_blue()`: Daemon thread med math.sin() for smooth wave
  - Respekterer `_blink_stop` event for clean shutdown
- **Wake word blokkering** (`duck_speech.py`):
  - Sleep check INNE i `wait_for_wake_word()` loop
  - Starter LED pulsing ved sleep, stopper ved wake
  - time.sleep(0.5) for responsiv oppvåkning
- **Main loop** (`chatgpt_voice.py`):
  - 0.5s polling interval for rask respons
  - `sleep_led_active` flag forhindrer multiple LED threads
  - `set_blue()` når våknet (ikke off())
- **AI tools** (`duck_ai.py`):
  - `enable_sleep_mode` og `disable_sleep_mode` function calling tools
  - System prompt inkluderer sleep status når aktiv
  - [AVSLUTT] marker i tool response for umiddelbar terminering
- **Web UI**: 
  - Dropdown med presets (30min, 1t, 2t, 3t, 4t)
  - Live countdown display
  - 1s polling (updateSleepModeStatus())

**API Endpoints**:
```http
GET  /sleep_status        # Hent sleep mode status
POST /sleep/enable        # Aktiver sleep mode (duration_minutes)
POST /sleep/disable       # Deaktiver sleep mode
```

**Resultat**: Perfekt for filmkvelder eller når du trenger stillhet! 🎬💤

#### 🔍 Web Search - Ferske nyheter og fakta

**Beskrivelse**: Anda kan nå søke på internett og lese faktisk innhold fra artikler, ikke bare lenker.

**Funksjoner**:
- **Brave Search API**: 2000 gratis søk per måned
- **Automatisk aktivering**: ChatGPT bestemmer når den trenger oppdatert info
- **Artikkel-skraping**: Leser faktisk innhold fra topp 2 resultater
- **BeautifulSoup parsing**: Ekstraherer main content fra HTML
- **Smart cleaning**: Fjerner scripts, styles, nav, footer, ads
- **Oppsummering**: Kombinerer søkeresultater med artikkelinnhold
- **Multiple sources**: Web results, news, FAQ sections

**Teknisk implementering**:
- **Brave Search API** (`src/duck_web_search.py`):
  - `web_search(query, count=5)`: Henter søkeresultater
  - `_fetch_article_content(url, max_length=1500)`: Skraper HTML med BeautifulSoup
  - Ekstraherer fra `<article>`, `<main>`, eller content divs
  - Regex-basert whitespace cleaning
  - Leser topp 2 artikler fullt, resten kun descriptions
- **AI Function Calling** (`duck_ai.py`):
  - `web_search` tool i function calling array
  - ChatGPT bestemmer selv når den trenger web search
  - Integrert i samtaleflyt uten eksplisitt kommando
- **Dependencies**: 
  - `requests` for HTTP calls
  - `beautifulsoup4>=4.12.0` for HTML parsing

**API Key Setup**:
1. Registrer på https://api.search.brave.com/register
2. Legg til i `.env`:
   ```
   BRAVE_SEARCH_API_KEY=your-api-key-here
   ```

**Eksempler**:
- "Hva er de siste nyhetene om AI?"
- "Finn informasjon om været i morgen"
- "Søk etter oppskrifter på brownies"
- "Hva skjer i verden akkurat nå?"

**Resultat**: Anda har nå tilgang til fersk informasjon fra hele nettet! 🌐📰

## [2.1.3] - 2026-01-15

### Ny funksjonalitet

#### ⚙️ Konfigurerbare Memory-innstillinger

**Beskrivelse**: Alle viktige minnessystem-innstillinger kan nå justeres direkte i kontrollpanelet!

**Nye sliders under "🧠 Andas Minne" → "⚙️ Minneinnstillinger"**:
1. **Max Kontekst Fakta** (1-200, default: 100)
   - Totalt antall fakta som sendes til AI i hver query
   - Øk for bedre kontekst, senk for raskere respons

2. **Embedding Søk Limit** (10-100, default: 30)
   - Hvor mange facts embedding-søket returnerer før expansion
   - Øk for bredere søk, senk for mer fokusert

3. **Minnegrense** (1-20, default: 8)
   - Antall episodiske minner som inkluderes i kontekst
   - Øk for mer samtalehistorikk, senk for kortere context

4. **Minne Threshold** (0.2-0.8, default: 0.35)
   - Similarity threshold for embedding search
   - Senk for flere treff, øk for mer relevante treff

**Funksjoner**:
- ✓/✗ status feedback ved lagring
- Lagres umiddelbart i database
- Brukes ved neste query (ingen restart nødvendig)
- Fallback til config-defaults hvis ikke satt
- Live preview av verdier mens du drar sliderne

**API Endpoints**:
```http
GET  /api/settings/memory              # Hent alle memory settings
POST /api/settings/memory              # Oppdater en eller flere settings
GET  /api/settings/max-context-facts   # Hent max context facts
POST /api/settings/max-context-facts   # Oppdater max context facts
```

**Teknisk implementering**:
- Ny `duck_config.py`: Sentral konfigurasjonsfil med MEMORY_* konstanter
- Settings lagres i `profile_facts` tabell med `topic='system'`
- `duck_memory.py` leser settings dynamisk fra database
- JavaScript-funksjoner for hver slider med live updates
- Backend validering av input-ranges

**Resultat**: Enkelt å eksperimentere med memory-systemet uten kodeendringer! 🎛️

## [2.1.2] - 2026-01-09

### Ny funksjonalitet

#### 💡 Philips Hue Smart Lys-integrasjon

**Beskrivelse**: Anda kan nå kontrollere Philips Hue smarte lys med stemmen!

**Funksjoner**:
- **På/Av kontroll**: Skru lys på eller av med stemmen
- **Lysstyrke**: Dimm eller skru opp lyset (0-100%)
- **8 farger**: rød, blå, grønn, gul, hvit, rosa, lilla, oransje
- **Rom-støtte**: Styr spesifikke lys eller alle samtidig
- **Intelligent matching**: Anda finner riktig lys basert på navn
- **Lokal API**: Alt skjer lokalt på nettverket (ingen sky)

**Eksempler**:
- "Skru på lyset" → Alle lys skrus på
- "Skru av lyset midt" → Lyset "Midt" skrus av
- "Gjør lyset rødt" → Endrer farge til rødt
- "Dimm lyset til 30 prosent" → Setter lysstyrke til 30%
- "Gjør lyset i stua grønt" → Endrer farge på stue-lys
- "Skru opp lyset" → Øker lysstyrke

**Teknisk implementering**:
- **OpenAI Function Calling**: ChatGPT bestemmer når den skal kontrollere lys
- **Philips Hue Bridge API**: Lokal REST API (ikke cloud-avhengig)
- **Hue color space**: Konverterer norske fargenavn til Hue/Sat verdier
- **Brightness mapping**: 0-100% → 0-254 (Hue-format)
- **Fuzzy matching**: Finner lys ved navn (case-insensitive substring search)
- **Multi-light support**: Kan styre flere lys samtidig

**Oppsett**:
1. Finn Bridge IP: `nmap -sn 192.168.x.0/24 | grep -B 2 Philips`
2. Generer API-nøkkel: Trykk link-knappen på Bridge, så:
   ```bash
   curl -X POST http://<bridge-ip>/api -d '{"devicetype":"duck_assistant"}'
   ```
3. Legg til i `.env`:
   ```
   HUE_BRIDGE_IP=192.168.10.120
   HUE_API_KEY=<din-api-key>
   ```

**Resultat**: Anda kan nå kontrollere alle dine smarte lys! 💡🎨

#### 👋 Automatisk retur til Wake Word ved takk

**Beskrivelse**: Når du takker anda for hjelpen, avslutter samtalen automatisk etter at anda har svart.

**Funksjoner**:
- **Intelligent takk-deteksjon**: Gjenkjenner "takk", "tusen takk", "mange takk" og "takker"
- **Høflig avslutning**: Anda svarer på takken før samtalen avsluttes
- **Automatisk wake word-modus**: Går direkte tilbake til å vente på "Samantha"
- **Naturlig samtaleflyt**: Slipper å si "stopp" for å avslutte

**Eksempel**:
- Du: "Hva er klokka?"
- Anda: "Klokken er 13:30"
- Du: "Takk!"
- Anda: "Bare hyggelig!"
- *Går automatisk tilbake til wake word-modus*

**Teknisk implementering**:
- Deteksjon i `chatgpt_query()` etter svar fra ChatGPT
- Returnerer tuple `(svar, is_thank_you)` i stedet for bare svar
- Main loop bryter ut av samtale når `is_thank_you=True`
- Case-insensitive matching på norske takk-uttrykk

**Resultat**: Mer naturlige samtaler - ingen behov for eksplisitt "stopp"-kommando! 👋

#### 💫 LED-pulsing når Nebb er Av

**Beskrivelse**: Når nebbet er deaktivert via kontrollpanelet, pulser LED-lysene i takt med talen i stedet!

**Funksjoner**:
- **Automatisk fallback**: LED tar over når nebb er av
- **Amplitude-basert pulsing**: LED-intensitet følger talens lydnivå
- **Samme synkronisering**: Bruker identisk teknikk som musikk-avspilling
- **Visuell feedback**: Du ser at anda snakker selv uten nebb-bevegelse
- **Toggle via kontrollpanel**: Skru nebb av/på i sanntid

**Eksempel**:
1. Åpne kontrollpanelet (http://pi-ip:3000)
2. Sett "Nebb" til "Av 🔇"
3. Si "Samantha, hva er klokka?"
4. Anda svarer med LED som pulser i takt med stemmen (nebb står stille)

**Teknisk implementering**:
- Delt thread-funksjon: `update_beak_or_led()`
- Sjekker `beak_enabled` flag fra `/tmp/duck_beak.txt`
- Hvis nebb på: `beak.open_pct(amplitude * 3.5)`
- Hvis nebb av: `set_intensity(amplitude * 4.0)`
- Samme timing og chunk-synkronisering som nebb-bevegelse
- Funker både for tale og sang-avspilling

**Resultat**: Anda gir alltid visuell feedback - enten med nebb eller LED! 💫🎤

#### �️ Stemme-kontroll av Nebb

**Beskrivelse**: Du kan nå skru nebbet av eller på ved å snakke med anda!

**Funksjoner**:
- **Stemme-kommandoer**: Si "nebb av" eller "nebb på" direkte til anda
- **OpenAI Function Calling**: ChatGPT gjenkjenner kommandoen automatisk
- **Bekreftelse**: Anda bekrefter endringen og forklarer hva som skjer
- **Umiddelbar effekt**: Endringen gjelder fra neste gang anda snakker
- **Persistens**: Innstillingen lagres i `/tmp/duck_beak.txt`

**Eksempler**:
- "Samantha, nebb av" → Anda: "Jeg har skrudd nebbet av. Jeg bruker LED-lys i stedet når jeg snakker."
- "Samantha, nebb på" → Anda: "Jeg har skrudd nebbet på. Nå beveger nebbet seg når jeg snakker."

**Teknisk implementering**:
- Ny funksjon: `control_beak(enabled)` skriver til `BEAK_FILE`
- OpenAI tool: `control_beak` med boolean parameter `enabled`
- Integrert i function calling handler i `chatgpt_query()`
- Fungerer sammen med LED-fallback funksjonen

**Resultat**: Sømløs kontroll av nebb - både via web og stemme! 🎙️🔧

#### �🌤️ Værmelding fra yr.no

**Beskrivelse**: Anda kan nå svare på spørsmål om været ved å hente live data fra yr.no (Meteorologisk institutt).

**Funksjoner**:
- **Automatisk stedsgjenkjenning**: Spør om været i en spesifikk by
- **Tidsramme-støtte**: "nå", "i dag" eller "i morgen"
- **Nåværende temperatur**: Henter live temperatur fra yr.no
- **Værbeskrivelse**: Beskriver nåværende vær (f.eks. "klarvær", "lett regn")
- **Prognose**: Viser temperatur utover dagen (neste 12 timer)
- **Morgendagens vær**: Min/max temperatur og værtype for hele morgendagen
- **Intelligent dialog**: Hvis du ikke nevner sted, spør anda hvor du lurer på været

**Eksempler**:
- "Hva er været i Sokndal?" → Nåværende vær + prognose i dag
- "Hva er været i Oslo i morgen?" → Min/max temp + værtype for morgendagen
- "Hvor varmt er det i Oslo nå?" → Nåværende temperatur
- "Hvordan blir været i Bergen i dag?" → Dagens prognose
- "Hva er været?" → Anda spør: "Hvor vil du vite været?"

**Teknisk implementering**:
- **OpenAI Function Calling**: ChatGPT bestemmer når den skal hente værdata
- **Tidsramme-parameter**: "now", "today", "tomorrow" - automatisk detektert
- **Nominatim geocoding**: Konverterer stedsnavn til koordinater (OpenStreetMap)
- **MET Norway API**: locationforecast/2.0 for værdata
- **Norsk oversettelse**: Symbolkoder oversettes automatisk til norsk
- **Morgendagsprognose**: Beregner min/max temp og mest vanlige værtype

**Resultat**: Anda gir nøyaktige værmeldinger for hele Norge - både nå og i morgen! 🌦️☀️

#### ⏰ Dato og Tid Bevissthet

**Beskrivelse**: ChatGPT kan nå svare på spørsmål om nåværende dato og tid ved å lese fra systemklokka.

**Funksjoner**:
- **Automatisk dato/tid injeksjon**: System prompt inkluderer alltid nåværende dato og tid
- **Norsk formatering**: "Torsdag 9. Januar 2026, klokken 11:53"
- **Naturlig dialog**: Anda kan svare på spørsmål som:
  - "Hva er klokka?"
  - "Hvilken dato er det?"
  - "Hvilken dag er det i dag?"
  - "Hvor lenge til midnatt?"

**Teknisk implementering**:
- `datetime.now()` henter systemtid ved hver ChatGPT-forespørsel
- **Norsk oversettelse**: Manuell mapping av engelske dag/månednavn til norsk
- Formateres som: "torsdag 9. januar 2026, klokken 13:57"
- Legges til i system prompt før personlighet
- Implementert i både `chatgpt_voice.py` og `duck-control.py`
- Dictionary-mapping for alle 7 dager og 12 måneder

**Resultat**: Anda vet alltid nøyaktig hvilken dato og tid det er - på norsk! 🕐📅

#### 🎵 Sang-avspilling med Nebb og LED Synkronisering

**Beskrivelse**: Anda kan nå synge sanger med synkronisert nebb-bevegelse og LED-pulsing!

**Funksjoner**:
- **Dual-file system**:
  - `duck_mix.wav`: Full mix av sang for avspilling
  - `vocals_duck.wav`: Isolert vokal-track for nebb-synkronisering
- **LED-pulsing**: LED pulser i takt med musikkens amplitude
- **Nebb-synkronisering**: Nebbet følger vokalens amplitude i sangtid
- **Artist/tittel-annonsering**: Anda sier artist og sangtittel før avspilling
- **Stereo/mono auto-detection**: Håndterer automatisk forskjellige audioformater
- **Sanntids synkronisering**: Progressbasert synkronisering av nebb og LED
- **Web-kontroll**: Start og stopp sanger via kontrollpanelet

**Teknisk implementering**:
- Separate threads for playback, LED-kontroll og nebb-kontroll
- Progressbasert mapping: `vocals_pos = (mix_idx / total_frames) * vocals_length`
- LED konverterer stereo til mono for amplitude-deteksjon
- Chunk size: 30ms (BEAK_CHUNK_MS) for smooth bevegelse
- IPC via `/tmp/duck_song_request.txt` og `/tmp/duck_song_stop.txt`

**Sangtilgang**: Web-kontrollpanel viser liste over alle tilgjengelige sanger i `musikk/` mappen.

**Resultat**: Anda synger med perfekt synkronisert nebb og pulserende LED!

### Forbedringer

#### 🎤 Audio Resampling for Porcupine

**Beskrivelse**: Implementert audio resampling for å håndtere forskjell mellom USB-mikrofon (48kHz) og Porcupine (16kHz).

**Endringer**:
- **scipy.signal.resample**: Konverterer 48000 Hz → 16000 Hz (3:1 ratio)
- **Buffer-størrelse**: 6144 samples (4x Porcupine frame length)
- **Stabilitetsgevinst**: Reduserer buffer overflow problemer
- **Logging**: Viser resampling-detaljer ved oppstart

**Resultat**: Porcupine wake word detection fungerer stabilt med USB-mikrofoner.

#### 🔇 Buffer Overflow Håndtering

**Beskrivelse**: Undertrykt buffer overflow advarsler som ikke påvirker funksjonalitet.

**Endringer**:
- Økt buffer-størrelse fra 1536 til 6144 samples
- Undertrykt PortAudio overflow warnings (`err_code = -9981`)
- Logging kun hvis ikke overflow (unngår logg-spam)

**Resultat**: Renere logger uten funksjonalitetstap.

#### 🎨 Stereo/Mono Auto-Detection

**Beskrivelse**: Automatisk håndtering av stereo og mono audio-filer.

**Endringer**:
- Detekterer antall kanaler i mix og vocals
- Åpner OutputStream med korrekt antall kanaler
- Konverterer vocals til mono for amplitude-deteksjon
- Konverterer mix til mono for LED-kontroll

**Resultat**: Sanger spilles med korrekt hastighet uavhengig av format.

### Dokumentasjonsoppdateringer

- **ARCHITECTURE.md**: Dokumentert sang-avspilling arkitektur
- **DOCUMENTATION.md**: Oppdatert statistikk og sist oppdatert dato
- **requirements.txt**: Lagt til scipy for resampling
- **README.md**: Dokumentert sang-funksjonalitet

## [2.1.1] - 2026-01-06

### Forbedringer

#### 🎤 Wake Word-teknologi Oppgradering

**Beskrivelse**: Byttet fra Vosk til Porcupine for mer pålitelig wake word-deteksjon.

**Endringer**:
- **Wake word endret**: Fra "Anda" til "Samantha"
- **Engine**: Picovoice Porcupine (erstatter Vosk)
- **Fordeler**:
  - Mer pålitelig deteksjon av wake word
  - Lavere CPU-bruk
  - Raskere responstid
  - Bedre støyreduksjon
- **Konfigurasjon**: Krever Picovoice API-nøkkel i `.env`
- **Uttale**: "Samantha" er lettere å gjenkjenne enn "Anda"

**Si "Samantha" for å starte en samtale!**

#### 🌐 Nettverksdeteksjon ved Oppstart

**Beskrivelse**: Anda annonserer nå tydeligere hvis den ikke klarer å koble til nettverket ved oppstart.

**Endringer**:
- Oppdatert oppstartsmelding når nettverket ikke er tilgjengelig
- **Gammel melding**: "Kvakk kvakk! Jeg er nå klar for andeprat. Nettverket er ikke tilgjengelig ennå, men jeg kan fortsatt snakke med deg."
- **Ny melding**: "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"
- Prøver å koble til nettverket i opptil 10 sekunder (5 forsøk × 2 sekunder)
- Gir tydeligere brukertilbakemelding om nettverksproblemer

#### 📚 Dokumentasjonsoppdateringer

**USB-C PD-trigger dokumentasjon**:
- Dokumentert bruken av USB-C PD-trigger med avklippet USB-C kabel for servo-strøm
- PCA9685 servo-kontroller kobles til PD-trigger for å få 5V strøm
- Dette unngår at servoen trekker strøm direkte fra Pi'en (forhindrer reboots)
- Oppdatert dokumentasjon i:
  - **README.md**: Hardware-seksjon og oppsett-diagram
  - **PINOUT.md**: Detaljert PD-trigger tilkoblings-informasjon
  - **INSTALL.md**: Installasjonsveiledning med PD-trigger oppsett
  - **ARCHITECTURE.md**: Hardware-arkitektur og strømforsyning
  - **DOCUMENTATION.md**: Søkeindeks oppdatert

**Fordeler med PD-trigger**:
- Kompakt løsning for servo-strøm
- Stabil 5V output
- Ingen eksterne strømforsyninger nødvendig
- Perfekt for integrasjon i lekeand

## [2.1.0] - 2025-11-11

### Ny funksjonalitet

#### 🌀 Automatisk Viftekontroll

**Beskrivelse**: Intelligent temperaturbasert kjøling for Raspberry Pi med 5V vifte på GPIO 13.

**Funksjoner**:
- **Automatisk modus**: 
  - Starter vifte når CPU-temperatur ≥ 55°C
  - Stopper vifte når CPU-temperatur ≤ 50°C
  - 5°C hysterese for å unngå flapping
- **Manuell overstyring**:
  - Auto: Automatisk temperaturbasert kontroll
  - På: Tving vifte til å alltid gå
  - Av: Tving vifte til å alltid stå
- **Web-kontrollpanel integrasjon**:
  - Tre knapper: Auto/På/Av
  - Sanntids temperaturvisning
  - Fargekodet temperatur (grønn < 55°C, orange < 60°C, rød ≥ 60°C)
  - Live status: Se om vifta går akkurat nå
  - Automatisk oppdatering hvert 5. sekund

**Teknisk implementering**:
- Ny service: `fan-control.service`
- Python-script: `fan_control.py`
- GPIO 13 (blå ledning fra Pi 5 vifte)
- IPC via `/tmp/duck_fan.txt` (modus) og `/tmp/duck_fan_status.txt` (status)
- API endpoints: `/fan-status` (GET) og `/set-fan-mode` (POST)

**Installasjon**: Inkludert i `install-services.sh`

## [2.0.1] - 2025-11-10

### Bugfixes

#### 🐛 Volumkontroll

**Problem**: Volumslideren i kontrollpanelet hadde ingen effekt på lydavspilling. Slideren kunne justeres, men volumet endret seg ikke når anda snakket.

**Årsak**: 
1. HTML slider mangler `oninput` event handler - visningen oppdaterte seg ikke under draing
2. `chatgpt_voice.py` leste aldri volumet fra `/tmp/duck_volume.txt`
3. Volumet ble ikke anvendt på lydsamplene før avspilling

**Løsning**:
- Lagt til `oninput="updateVolumeValue()"` i HTML slider for sanntidsoppdatering av visning
- Lagt til `VOLUME_FILE = "/tmp/duck_volume.txt"` konstant i `chatgpt_voice.py`
- Implementert volumlesing i `speak()` funksjonen (0-100, hvor 50 = normal)
- Konverterer volumverdien til gain multiplier (0.0-2.0 hvor 1.0 = normal)
- Anvender volumet på lydsamplene etter fade-in/fade-out: `samples = samples * volume_gain`
- Lagt til voluminfo i TTS-logging: `Volum: 50% (gain: 1.00)`

**Resultat**: Volumkontroll fungerer nå som forventet - 0% = stille, 50% = normalt, 100% = dobbelt lydstyrke.

## [2.0.0] - 2025-11-10

### Major Release: Web Control Panel & Enhanced Features

#### 🎉 Nye hovedfunksjoner

##### Web Kontrollpanel (Port 3000)
- **Komplett web-basert kontrollpanel** for fjernstyring av alle funksjoner
- **Sanntids statusvisning** med automatisk oppdatering hvert 5. sekund
- **Live systemlogger** med fargekodet output (grønn/rød/orange)
- **Smart scroll** i logger - auto-scroll kun hvis bruker er nederst
- **Service-kontroll** via web (start/stopp/restart chatgpt-duck.service)
- **Responsive design** med gradient styling og smooth animasjoner

##### Talehastighet-kontroll
- **Justerbar talehastighet** via slider (0-100%)
  - 0%: Veldig sakte (–50% hastighet)
  - 50%: Normal hastighet
  - 100%: Dobbel hastighet (+100%)
- **SSML prosody rate** implementering i Azure TTS
- **Synkron nebb-bevegelse** justeres automatisk til hastighet
- **Persistent lagring** via `/tmp/duck_speed.txt`

##### Volumkontroll
- **Sanntids volumjustering** (0-100%)
- **Visuell slider** med "Lavt 🔉" og "Høyt 🔊" labels
- **Persistent lagring** via `/tmp/duck_volume.txt`
- **Live preview** av volumnivå i prosent

##### AI og Stemmeinnstillinger
- **Modellvalg** (gpt-3.5-turbo, gpt-4, gpt-4-turbo)
- **5 personligheter**:
  - Normal (balansert og høflig)
  - Entusiastisk (energisk og positiv)
  - Filosofisk (reflekterende og dyp)
  - Humoristisk (morsom og spøkefull)
  - Kort (konsise svar)
- **3 norske Azure TTS stemmer**:
  - nb-NO-FinnNeural (mann, dyp)
  - nb-NO-PernilleNeural (kvinne, klar)
  - nb-NO-IselinNeural (kvinne, varm)

##### Direktemeldinger
- **Tre moduser** for sending:
  - 🔊 Bare si det (TTS uten AI)
  - 🤖 Send til ChatGPT (stille respons)
  - 🎯 Full behandling (AI + TTS + nebb)
- **Stort tekstfelt** med gradient styling
- **Real-time feedback** ved sending

##### System-administrasjon
- **WiFi-scanning** med visning av tilgjengelige nettverk
- **Hotspot-switch** for WiFi-konfigurasjon
- **System reboot** via web
- **System shutdown** via web
- **Nebb-test** funksjon

#### 🔧 Tekniske forbedringer

##### Backend (duck-control.py)
- **15 nye REST API endpoints**:
  - GET `/duck-status` - Service running status
  - GET `/status` - Alle innstillinger
  - GET `/logs` - Systemlogger via journalctl
  - GET `/current-model`, `/current-personality`, `/current-voice`, etc.
  - GET `/wifi-networks` - Scan WiFi (nmcli integration)
  - POST `/control` - Service-kontroll
  - POST `/change-speed`, `/change-volume`, etc.
  - POST `/speak`, `/ask`, `/full-response` - Meldings-moduser
  - POST `/test-beak` - Test nebb-bevegelse
  - POST `/reboot`, `/shutdown` - System-kontroll
- **BaseHTTPRequestHandler** implementering (ingen eksterne web-dependencies)
- **JSON response format** standardisering
- **Error handling** med detaljerte feilmeldinger
- **Sudo-rettigheter** konfigurert via `/etc/sudoers.d/duck-control`

##### Frontend (JavaScript)
- **Async/await** for alle API-kall
- **Error handling** med user-friendly meldinger
- **Smart UI updates**:
  - Auto-refresh status (5s interval)
  - Color-coded log lines (regex-basert parsing)
  - Smooth scroll behavior
  - Form validation
- **No external dependencies** - vanilla JavaScript

##### IPC (Inter-Process Communication)
- **Tmp-fil basert kommunikasjon** mellom services:
  - `/tmp/duck_personality.txt` - AI-personlighet
  - `/tmp/duck_voice.txt` - Azure TTS stemme
  - `/tmp/duck_volume.txt` - Lydvolum (0-100)
  - `/tmp/duck_beak.txt` - Nebb on/off
  - `/tmp/duck_speed.txt` - Talehastighet (0-100)
  - `/tmp/duck_model.txt` - ChatGPT-modell
  - `/tmp/duck_message.txt` - Direktemeldinger
- **Atomic file writes** for race condition prevention
- **Default values** hvis filer mangler

##### Hovedapplikasjon (chatgpt_voice.py)
- **Speed parameter** i TTS-funksjon med SSML prosody
- **Volume control** integrering
- **Dynamic config loading** fra tmp-filer
- **Improved error handling** med retry logic

#### 🎨 UI/UX Forbedringer

##### Styling
- **Gradient backgrounds** (purple/blue theme)
- **Smooth animations** på buttons og hover
- **Color-coded status badges**:
  - Grønn: Duck kjører ✅
  - Rød: Duck stoppet ⏸️
  - Gul: Ukjent status ❓
- **Terminal-style logger** med monospace font og #1e1e1e bakgrunn
- **Full-width sliders** med emoji labels
- **Responsive layout** for mobile og desktop

##### Interaktivitet
- **Real-time feedback** på alle handlinger
- **Loading states** under API-kall
- **Confirmation dialogs** for critical actions
- **Auto-update** av UI etter endringer

#### 📚 Dokumentasjon

##### Nye dokumenter
- **ARCHITECTURE.md** - Komplett teknisk arkitektur
  - Komponentbeskrivelse
  - Data flow diagrammer
  - IPC-protokoll detaljer
  - API endpoint dokumentasjon
  - Sikkerhet og rettigheter
  - Feilhåndtering
  - Performance metrics
  - Debugging guide

- **INSTALL.md** - Detaljert installasjonsveiledning
  - Hardware-oppsett med wiring-diagrammer
  - Software-installasjon steg-for-steg
  - API-nøkkel konfigurasjon
  - Systemd service setup
  - Test og verifisering
  - Feilsøkingsseksjon
  - Vedlikeholdsinstruksjoner

- **PORTS.md** - Nettverks- og port-konfigurasjon
  - Detaljert port-dokumentasjon
  - GPIO pin mapping
  - Brannmur-konfigurasjon
  - Ekstern tilgang via VPN
  - Feilsøking nettverksproblemer

##### Oppdaterte dokumenter
- **README.md** - Komplett omskriving
  - Hovedfunksjoner oversikt
  - Web kontrollpanel guide
  - RGB LED status-tabell
  - Stemmekommandoer
  - Systemkrav
  - IPC-protokoll tabell
  - API endpoint oversikt

- **requirements.txt** - Med kommentarer og versjoner
  - Gruppering per funksjon
  - Minimum versjoner spesifisert
  - Forklaringer for hver pakke

#### 🔒 Sikkerhet

- **Sudo-restriksjoner** via sudoers-fil
- **API-nøkkel isolasjon** i .env (ikke committet)
- **Input validation** på alle POST endpoints
- **Timeout protection** på subprocess-kall
- **Error sanitization** i responses

#### 🐛 Bugfixes

- **Fixed: JavaScript response checking** (data.status → data.success)
- **Fixed: Double scrollbars** i logger
- **Fixed: Log auto-scroll** interrupting reading
- **Fixed: Box width alignment** med box-sizing: border-box
- **Fixed: Missing favicon** (404 error)
- **Fixed: Status ikke oppdatert** ved pageload
- **Fixed: Newline escaping** i JavaScript-generert kode

#### ⚡ Performance

- **Reduced API calls** med caching av innstillinger
- **Debounced slider updates** for mindre disk I/O
- **Efficient log fetching** med journalctl -n 50
- **Minimal JavaScript** (no frameworks overhead)

#### 🔄 Breaking Changes

Ingen breaking changes - bakoverkompatibel med versjon 1.x.

Eksisterende installasjoner kan oppgraderes med:
```bash
git pull
sudo systemctl restart duck-control.service
sudo systemctl restart chatgpt-duck.service
```

---

## [1.0.0] - 2025-10-XX

### Initial Release

#### Core Features
- Wake word detection med Porcupine ("Samantha")
- Azure Speech-to-Text for stemmegjenkjenning
- ChatGPT integration via OpenAI API
- Azure Text-to-Speech med norske stemmer
- Servo-kontrollert nebb med amplitude-synkronisering
- RGB LED status-indikatorer
- Systemd service for auto-start

#### Hardware Support
- Raspberry Pi 4/5/400
- Monk Makes RGB LED
- SG90/MG90 servo
- USB mikrofon
- 3.5mm/HDMI/USB høyttaler

#### AI Capabilities
- Contextual conversation med historikk
- Single personality (normal)
- Single voice (nb-NO-FinnNeural)
- gpt-3.5-turbo modell

#### Configuration
- Environment variables via .env
- Manual configuration av innstillinger
- Command-line scripts for setup

---

## Versjonsnummerering

Prosjektet følger [Semantic Versioning](https://semver.org/):
- **MAJOR** version for inkompatible API-endringer
- **MINOR** version for nye funksjoner (bakoverkompatibel)
- **PATCH** version for bugfixes (bakoverkompatibel)

---

## Kommende funksjoner (Roadmap)

### Version 2.1.0 (Planlagt)
- [ ] WebSocket for real-time log streaming (no polling)
- [ ] Custom wake word training
- [ ] Conversation history database (SQLite)
- [ ] Export/import av innstillinger
- [ ] Voice activity detection (VAD) forbedringer
- [ ] Multi-language support (engelsk, tysk, etc.)

### Version 2.2.0 (Planlagt)
- [ ] MQTT integration for smart home
- [ ] Scheduled tasks (reminders, alarms)
- [ ] Weather integration
- [ ] Calendar integration
- [ ] News reading capability

### Version 3.0.0 (Fremtidig)
- [ ] Local LLM support (Ollama, LLaMA)
- [ ] Whisper STT (lokal stemmegjenkjenning)
- [ ] Docker deployment option
- [ ] Multi-user profiles
- [ ] Voice authentication
- [ ] Mobile app (iOS/Android)

---

**Bidrag velkommen!** Se [CONTRIBUTING.md](CONTRIBUTING.md) for retningslinjer.
