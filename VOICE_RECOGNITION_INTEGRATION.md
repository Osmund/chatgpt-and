━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOICE RECOGNITION - SAMANTHA INTEGRASJONSGUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dato: 8. februar 2026
Fra: Duck-Vision (Pi 5 - oDuckberry-vision.local)
Til: Samantha (Pi 4 - oDuckberry-2.local)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


█ HVA ER NYTT?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Duck-Vision har nå en mikrofon og passiv stemmegjenkjenning!

Hvordan det fungerer:
1. Mikrofonen lytter kontinuerlig i bakgrunnen
2. VAD (Voice Activity Detection) filtrerer ut stillhet
3. Når noen snakker, genereres en "stemme-fingerprint"
4. Fingerprint matches mot kjente stemmeprofiler

Automatisk profilbygging:
- Når face detection gjenkjenner en person UTEN stemmeprofil
- Og det er KUN én person foran kameraet
- Så samler Duck-Vision stemmedata i bakgrunnen (~10-15 sek tale)
- Profilen lagres automatisk - personen merker ingenting!

Neste gang kan Duck-Vision identifisere personen via stemme alene
(f.eks. når ansiktet ikke er synlig, dårlig lys, bortvendt, osv.)


█ NYE MQTT TOPICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Samantha må subscribe på: duck/audio/#

To nye topics:

┌──────────────────────────────────────────────────────────────────────┐
│  duck/audio/speaker                                                  │
│  ─────────────────                                                   │
│  Publiseres når en stemme gjenkjennes.                               │
│                                                                      │
│  Payload:                                                            │
│  {                                                                   │
│    "event": "speaker_recognized",                                    │
│    "timestamp": 1707400000.0,                                        │
│    "name": "Åsmund",                                                 │
│    "confidence": 0.847,                                              │
│    "speech_duration": 3.2                                            │
│  }                                                                   │
│                                                                      │
│  Cooldown: Maks ett event per person per 15 sekunder.                │
│  Confidence: 0.0-1.0 (terskel er 0.75)                               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  duck/audio/voice_learned                                            │
│  ────────────────────────                                            │
│  Publiseres når en stemmeprofil er opprettet (automatisk eller       │
│  manuelt).                                                           │
│                                                                      │
│  Payload:                                                            │
│  {                                                                   │
│    "event": "voice_profile_created",                                 │
│    "timestamp": 1707400060.0,                                        │
│    "name": "Åsmund",                                                 │
│    "success": true,                                                  │
│    "speech_duration": 12.3                                           │
│  }                                                                   │
└──────────────────────────────────────────────────────────────────────┘


█ NY KOMMANDO (VALGFRI)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Samantha kan be Duck-Vision lære en stemme manuelt:

  Topic: duck/samantha/commands
  Payload:
  {
    "command": "learn_voice",
    "name": "Åsmund",
    "duration": 10.0
  }

Personen må snakke i ~10 sekunder. Resultat kommer på
duck/audio/voice_learned.

Vanligvis er dette IKKE nødvendig - profiler bygges automatisk
når ansiktet gjenkjennes.


█ VIKTIG: MUTING NÅR SAMANTHA SNAKKER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Duck-Vision sin mikrofon vil fange opp Samanthas stemme fra
høyttaleren. For å unngå at Anda sin stemme blir tolket som en
ekte person (eller enda verre - at det lages en stemmeprofil av
henne), MÅ Samantha sende mute/unmute-signaler.

  Topic: duck/samantha/speaking

  Når Samantha BEGYNNER å snakke (rett FØR TTS starter):
  {"speaking": true}

  Når Samantha er FERDIG med å snakke (rett ETTER TTS er ferdig):
  {"speaking": false}

Duck-Vision forkaster ALL audio mellom true og false.

┌──────────────────────────────────────────────────────────────────────┐
│  KODEEKSEMPEL FOR SAMANTHA:                                          │
│                                                                      │
│  def speak(text, speech_config, beak):                               │
│      # Mute Duck-Vision mikrofon                                     │
│      mqtt_client.publish("duck/samantha/speaking",                   │
│          json.dumps({"speaking": True}))                             │
│                                                                      │
│      # ... eksisterende TTS-kode ...                                 │
│      do_tts(text, speech_config, beak)                               │
│                                                                      │
│      # Unmute Duck-Vision mikrofon                                   │
│      mqtt_client.publish("duck/samantha/speaking",                   │
│          json.dumps({"speaking": False}))                            │
└──────────────────────────────────────────────────────────────────────┘


█ ENDRET EKSISTERENDE EVENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check_person_result har fått et nytt felt:

  {
    "event": "check_person_result",
    "data": {
      "found": true,
      "name": "Åsmund",
      "confidence": 0.87,
      "has_voice_profile": true         ← NYTT FELT
    }
  }

forget_person sletter nå også stemmeprofilen automatisk.
Ingen endring nødvendig på Samantha-siden for dette.


█ ANBEFALT OPPFØRSEL: NÅR PROFILER ER KLARE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stemmeprofiler bygges automatisk i bakgrunnen, uten at brukeren
merker noe. Samantha bør vurdere hvordan hun informerer brukeren.

Tre anbefalte strategier:

  1. SI DET MED EN GANG (enklest)
     Når duck/audio/voice_learned mottas med success=true:
     → "Nå kjenner jeg også stemmen din, Åsmund!"

     Fordel: Brukeren vet det med en gang.
     Ulempe: Kan komme midt i en samtale.

  2. SI DET NESTE GANG PERSONEN KOMMER (mest naturlig)
     Lagre at stemmeprofil er ny. Neste gang face_recognized
     eller speaker_recognized kommer for denne personen:
     → "Hei Åsmund! Nå kjente jeg deg igjen på stemmen også."

     Fordel: Naturlig samtalepunkt.
     Ulempe: Litt mer state å holde styr på.

  3. ALDRI SI NOE (stille forbedring)
     Bare bruk stemmeprofilen internt for høyere confidence.
     Brukeren merker bare at gjenkjenningen er blitt bedre.

     Fordel: Minst mulig forstyrrelse.
     Ulempe: Brukeren vet ikke at stemmen er lagret.

Anbefaling: Strategi 1 eller 2 - brukeren bør vite at stemmen
lagres, av hensyn til samtykke og transparens.

Eksempel for strategi 2:

```python
# Hold styr på nye stemmeprofiler
new_voice_profiles = set()

# Når stemmeprofil opprettes
elif topic == "duck/audio/voice_learned":
    name = data.get("name")
    if data.get("success"):
        new_voice_profiles.add(name)

# Neste gang personen gjenkjennes (ansikt eller stemme)
elif topic == "duck/audio/speaker" or (topic == "duck/vision/events" 
        and data.get("event") == "face_recognized"):
    name = data.get("name") or data.get("data", {}).get("name")
    if name in new_voice_profiles:
        speak(f"Hei {name}! Nå kjenner jeg deg også på stemmen.")
        new_voice_profiles.discard(name)
```


█ HVA SAMANTHA MÅ GJØRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Subscribe på duck/audio/# (i tillegg til duck/vision/#)
2. Håndtere speaker_recognized og voice_profile_created events
3. Sende mute/unmute på duck/samantha/speaking rundt all TTS
4. Sende conversation start/stop på duck/samantha/conversation
   ved wake word og samtaleslutt (ANBEFALT)
5. Det er alt! Alt annet er bakoverkompatibelt.


█ KODEEKSEMPEL FOR SAMANTHA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# ──────────────────────────────────────────────────────────
# 1. Legg til i MQTT subscribe (der du allerede har duck/vision/#)
# ──────────────────────────────────────────────────────────

client.subscribe("duck/audio/#")


# ──────────────────────────────────────────────────────────
# 2. Legg til i din on_message handler
# ──────────────────────────────────────────────────────────

def on_message(client, userdata, msg):
    topic = msg.topic
    data = json.loads(msg.payload.decode())

    # ... eksisterende duck/vision/* håndtering ...

    # Stemme gjenkjent (passiv, i bakgrunnen)
    if topic == "duck/audio/speaker":
        name = data.get("name")
        confidence = data.get("confidence", 0)
        print(f"🔊 Stemme gjenkjent: {name} ({confidence:.0%})")

        # VALGFRITT: Bruk som ekstra kontekst
        # F.eks. oppdater "hvem er i rommet"-state
        # Eller si noe hvis personen ikke er sett via kamera:
        # speak(f"Jeg hører at det er {name}!")

    # Stemmeprofil automatisk opprettet
    elif topic == "duck/audio/voice_learned":
        name = data.get("name")
        success = data.get("success", False)
        if success:
            print(f"✅ Stemmeprofil opprettet for {name}")
            # VALGFRITT: Informer brukeren
            # speak(f"Nå kjenner jeg også stemmen din, {name}!")


# ──────────────────────────────────────────────────────────
# 3. VALGFRITT: Manuell stemmelæring
# ──────────────────────────────────────────────────────────

def learn_voice(name, duration=10.0):
    """Be Duck-Vision om å lære en persons stemme"""
    command = {
        "command": "learn_voice",
        "name": name,
        "duration": duration
    }
    client.publish("duck/samantha/commands", json.dumps(command))
```


█ TESTING FRA COMMAND LINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Lytt på alle audio-events fra Duck-Vision:
mosquitto_sub -h oDuckberry-vision.local -t "duck/audio/#" -v

# Lytt på ALT (vision + audio):
mosquitto_sub -h oDuckberry-vision.local -t "duck/#" -v

# Trigger manuell stemmelæring:
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/commands \
  -m '{"command":"learn_voice", "name":"Åsmund", "duration":10}'

# Test samtale-modus (simuler wake word):
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/conversation \
  -m '{"active": true}'
# ... før samtale ... så avslutt:
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/conversation \
  -m '{"active": false}'

# Test muting (simuler at Samantha snakker):
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/speaking \
  -m '{"speaking": true}'
# ... vent litt ...
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/speaking \
  -m '{"speaking": false}'


█ ARKITEKTUR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────┐
│  DUCK-VISION (Pi 5)                                                 │
│                                                                     │
│  ┌──────────────┐   ┌────────────────────┐                          │
│  │ IMX500 Camera │   │ USB Mikrofon       │                          │
│  │ (ansikt/obj)  │   │ (48kHz, mono)      │                          │
│  └──────┬───────┘   └────────┬───────────┘                          │
│         │                    │                                       │
│         ▼                    ▼                                       │
│  ┌──────────────┐   ┌────────────────────┐                          │
│  │ Face Recog   │   │ Speaker Recog      │                          │
│  │ (hybrid)     │   │ • VAD (WebRTC)     │                          │
│  └──────┬───────┘   │ • Resample 48→16k  │                          │
│         │           │ • Resemblyzer embed │                          │
│         │           └────────┬───────────┘                          │
│         │                    │                                       │
│         ▼                    ▼                                       │
│  ┌─────────────────────────────────────┐                            │
│  │         duck_vision.py              │                            │
│  │  • Face match + no voice profile?   │                            │
│  │    → start auto-enrollment          │                            │
│  │  • ~10s tale samlet → lagre profil  │                            │
│  └──────────────┬──────────────────────┘                            │
│                 │                                                    │
│                 ▼  MQTT                                              │
│  duck/vision/events  ──── face_recognized, check_person_result      │
│  duck/audio/speaker  ──── speaker_recognized                        │
│  duck/audio/voice_learned ── voice_profile_created                  │
│                                                                     │
└────────────────────────────┐┌────────────────────────────────────────┘
                             │
                    MQTT (oDuckberry-2.local:1883)
                             │
┌────────────────────────────┴────────────────────────────────────────┐
│  SAMANTHA (Pi 4)                                                    │
│                                                                     │
│  Lytter på:                                                         │
│    duck/vision/#  (eksisterende)                                    │
│    duck/audio/#   (NYTT)                                            │
│                                                                     │
│  Publiserer:                                                        │
│    duck/samantha/commands  (eksisterende)                           │
│    duck/samantha/speaking  (NYTT - mute/unmute rundt TTS)           │
│    duck/samantha/conversation (NYTT - samtale start/stopp)          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
