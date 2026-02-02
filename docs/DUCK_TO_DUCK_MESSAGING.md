# Duck-to-Duck Messaging

Ender kan sende meldinger til hverandre via SMS Relay uten SMS-kostnad, med intelligent loop-prevention, token budgets og memory integration.

## Oversikt

**Problem:** SMS koster penger, og ender burde kunne snakke sammen gratis.

**Løsning:** Duck-to-duck messaging via SMS Relay server med:
- ✅ Gratis HTTP kommunikasjon (ingen SMS-kostnad)
- ✅ Token budget tracking (max 10 initiated/dag, 20 total/dag)
- ✅ Loop detection (similarity + rapid message detection)
- ✅ Memory integration (lagres som vanlige messages)
- ✅ Audio announcements ("Jeg har fått en melding fra min søster Seven")
- ✅ Smart auto-response med AI
- ✅ Voice command: "send melding til Seven"
- ✅ Web UI: Duck messages vises sammen med SMS i kontrollpanel

## Arkitektur

```
┌─────────────┐                    ┌─────────────┐
│  Samantha   │                    │    Seven    │
│   (Duck 1)  │                    │   (Duck 2)  │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ POST /duck/send                  │
       │ {"from_duck": "samantha",        │
       │  "to_duck": "seven",             │
       │  "message": "Hi!"}               │
       │                                  │
       ▼                                  │
┌─────────────────────────────────────────┴──────┐
│         SMS Relay Server                       │
│         (sms-relay.duckberry.no)               │
│                                                │
│  DUCK_TO_DUCK_QUEUE = {                        │
│    "seven": [{from: "samantha", msg: "Hi!"}]   │
│  }                                             │
└────────────────────────────────────────────────┘
                                  ▲
                                  │
                                  │ GET /duck/poll/seven
                                  │
                            ┌─────┴──────┐
                            │   Seven    │
                            │  polls q5s │
                            └────────────┘
```

## API Endpoints

### SMS Relay Server

#### POST /duck/send
Send melding til annen and.

**Request:**
```json
{
  "from_duck": "samantha",
  "to_duck": "seven",
  "message": "Hei Seven! Hvordan går det?",
  "media_url": "https://example.com/image.jpg"  // optional
}
```

**Response:**
```json
{
  "status": "queued",
  "from": "samantha",
  "to": "seven",
  "queue_size": 1
}
```

#### GET /duck/poll/{duck_name}
Poll for meldinger fra andre ender.

**Response:**
```json
{
  "status": "ok",
  "messages": [
    {
      "from_duck": "samantha",
      "to_duck": "seven",
      "message": "Hei Seven!",
      "media_url": null,
      "timestamp": "2026-02-02T20:30:15.123456",
      "id": "duck_1738525815.123456"
    }
  ],
  "count": 1
}
```

## Python API

### DuckMessenger (src/duck_messenger.py)

Hovedklasse for intelligent duck messaging med loop prevention.

```python
from src.duck_messenger import DuckMessenger

messenger = DuckMessenger()

# Sjekk om vi kan initiere melding
can_send, reason = messenger.can_initiate_message(boredom_level=5.0)
if can_send:
    # Send message via SMSManager
    from src.duck_sms import SMSManager
    sms = SMSManager()
    sms.send_duck_message("seven", "Hei!")
    
    # Log it
    messenger.log_message(
        from_duck="samantha",
        to_duck="seven", 
        message="Hei!",
        direction='sent',
        initiated=True
    )

# Sjekk for loop
if messenger.detect_loop("seven", new_message):
    print("Loop detected!")

# Get daily stats
stats = messenger.get_daily_stats()
# {'total_messages': 5, 'initiated': 2, 'tokens_used': 150, ...}

# Format announcement
announcement = messenger.format_incoming_announcement("seven", "Hei!")
# "Jeg har fått en melding fra min søster Seven. Den sier: Hei!"
```

### SMSManager (src/duck_sms.py)

```python
from src.duck_sms import SMSManager

sms = SMSManager()

# Send message to Seven
result = sms.send_duck_message(
    to_duck="seven",
    message="Hei Seven! Hvordan går det?",
    media_url=None  # optional
)

# Poll for messages (called automatically in background)
messages = sms.poll_duck_messages()
for msg in messages:
    print(f"From {msg['from_duck']}: {msg['message']}")

# Get other ducks
other_ducks = sms.get_duck_contacts()
# ['seven'] (hvis self er samantha)
```

## Implementering

### 1. SMS Relay Deployment

SMS relay må være deployed med nye endpoints. Dette er allerede gjort:

```bash
cd sms-relay
zip ../deploy.zip app.py requirements.txt .deployment
az webapp deploy \
  --resource-group og-sms-relay-rg \
  --name duck-sms-relay \
  --src-path ../deploy.zip \
  --type zip
```

✅ Status: https://sms-relay.duckberry.no/health

### 2. Duck Files Needed

**Nye filer:**
- `src/duck_messenger.py` - Loop prevention og token tracking

**Modifiserte filer:**
- `chatgpt_voice.py` - Integrert polling i SMS polling loop
- `src/duck_sms.py` - Send/poll duck messages

### 3. Polling Integration (chatgpt_voice.py)

Duck message polling er **integrert i SMS polling** - ingen separat thread nødvendig!

```python
def sms_polling_loop():
    """Poll for SMS and duck messages every 10 seconds"""
    from duck_sms import SMSManager
    from duck_messenger import DuckMessenger
    
    sms_manager = SMSManager()
    messenger = DuckMessenger()
    
    while True:
        time.sleep(10)
        
        # 1. Poll SMS messages (existing)
        # ... SMS handling code ...
        
        # 2. Poll duck-to-duck messages
        try:
            duck_messages = sms_manager.poll_duck_messages()
            
            for msg in duck_messages:
                from_duck = msg['from_duck']
                message_text = msg['message']
                
                # Check for loop
                if messenger.detect_loop(from_duck, message_text):
                    continue
                
                # Format announcement
                announcement = messenger.format_incoming_announcement(
                    from_duck, message_text
                )
                
                # Write to file for main loop to speak
                with open('/tmp/duck_message_announcement.txt', 'w') as f:
                    f.write(json.dumps({
                        'announcement': announcement,
                        'from_duck': from_duck,
                        'message': message_text
                    }))
                
                # Log received message
                messenger.log_message(
                    from_duck=from_duck,
                    to_duck=os.getenv('DUCK_NAME').lower(),
                    message=message_text,
                    direction='received'
                )
                
                # Generate AI response
                response = generate_duck_response(from_duck, message_text)
                
                # Send reply
                sms_manager.send_duck_message(from_duck, response)
                
                # Log sent message
                messenger.log_message(
                    from_duck=os.getenv('DUCK_NAME').lower(),
                    to_duck=from_duck,
                    message=response,
                    direction='sent',
                    tokens_used=len(response.split())
                )
                
                # Save to memory
                memory_manager.save_message(
                    user_text=f"[Duck message from {from_duck}]: {message_text}",
                    ai_response=response,
                    user_name=from_duck,
                    metadata=json.dumps({'type': 'duck_message'})
                )
        
        except Exception as e:
            print(f"Duck polling error: {e}")
```

### 4. Main Loop Integration

I main loop, sjekk for duck message announcements:

```python
# I main while loop (chatgpt_voice.py ca linje 960)
duck_msg_file = '/tmp/duck_message_announcement.txt'
if os.path.exists(duck_msg_file):
    try:
        with open(duck_msg_file, 'r') as f:
            data = json.loads(f.read())
        os.remove(duck_msg_file)
        
        announcement = data.get('announcement')
        if announcement:
            print(f"🦆💬 Duck message: {announcement[:50]}...")
            speak(announcement, speech_config, beak)
    except Exception as e:
        print(f"Error reading duck message: {e}")
```

### 2. Voice Command for Sending

✅ **IMPLEMENTERT** - Voice command er nå tilgjengelig!

Brukere kan si: **"send melding til Seven"** og AI-en vil kalle `send_duck_message` tool.

Tool er definert i `src/duck_ai.py`:

```python
{
    "type": "function",
    "function": {
        "name": "send_duck_message",
        "description": "Send en melding til en annen and (duck). Bruk dette når brukeren eksplisitt ber deg sende melding til en annen and, f.eks. 'send melding til Seven'. Sjekker token-budsjett automatisk.",
        "parameters": {
            "type": "object",
            "properties": {
                "duck_name": {
                    "type": "string",
                    "description": "Navnet på anden (f.eks. 'Seven', 'Samantha')"
                },
                "message": {
                    "type": "string",
                    "description": "Meldingen som skal sendes (maks 500 tegn)"
                }
            },
            "required": ["duck_name", "message"]
            "properties": {
                "to_duck": {
                    "type": "string",
                    "enum": ["samantha", "seven"],
                    "description": "Name of the recipient duck"
                },
                "message": {
                    "type": "string",
                    "description": "Message to send"
                }
            },
            "required": ["to_duck", "message"]
        }
    }
}
```

Handler:

```python
elif tool_name == "send_duck_message":
    to_duck = args.get('to_duck')
    message = args.get('message')
    
    result = sms_manager.send_duck_message(to_duck, message)
    tool_results.append({
        'tool_call_id': tool_call.id,
        'output': json.dumps(result)
    })
```

## Konfigurasjon for Seven

### 1. .env

```bash
# SMS Relay URL (samme som Samantha)
SMS_RELAY_URL=https://sms-relay.duckberry.no

# Duck name - VIKTIG: må være "Seven"
DUCK_NAME=Seven

# OpenAI for AI responses
OPENAI_API_KEY=your_key_here
```

### 2. Duck Relations (src/duck_messenger.py)

Oppdater relasjoner for Seven:

```python
DUCK_RELATIONS = {
    'samantha': 'min søster Samantha',  # Seven -> Samantha
    'seven': 'min søster Seven',        # Samantha -> Seven
    'oslo-duck': 'and-vennen min i Oslo'
}
```

### 3. Duck Contacts (src/duck_sms.py)

```python
def get_duck_contacts(self) -> List[str]:
    """Get list of other ducks"""
    all_ducks = ['samantha', 'seven']  # Legg til flere her
    return [d for d in all_ducks if d.lower() != self.duck_name.lower()]
```

## Web Kontrollpanel

✅ **IMPLEMENTERT** - Duck messages vises nå sammen med SMS!

### Visning

Duck messages vises i **SMS Historikk** seksjonen i kontrollpanelet sammen med vanlige SMS-er:

- 🦆 **Duck-ikon** (vs 📩📤 for SMS)
- 🟠 **Oransje styling** (vs blå/grønn for SMS)
- **Formattering:** "Seven → Samantha" (viser fra/til)
- **Kronologisk:** Sortert sammen med SMS etter tidsstempel

### Database Query

Endpoint `/sms_history` i `duck-control.py` bruker UNION ALL:

```python
SELECT 
    h.id, h.direction, h.message, h.timestamp,
    h.status, c.name, c.phone, 'sms' as message_type
FROM sms_history h
LEFT JOIN sms_contacts c ON h.contact_id = c.id

UNION ALL

SELECT
    d.id, d.direction, d.message, d.timestamp,
    'delivered' as status,
    d.from_duck || ' → ' || d.to_duck as name,
    NULL as phone, 'duck' as message_type
FROM duck_messages d

ORDER BY timestamp DESC
LIMIT 100
```

### JavaScript (templates/app.js)

```javascript
const isDuckMessage = sms.message_type === 'duck';
const icon = isDuckMessage ? '🦆' : (isIncoming ? '📩' : '📤');
const bgColor = isDuckMessage 
    ? (isIncoming ? '#fff3e0' : '#ffe0b2')  // Orange tones
    : (isIncoming ? '#e3f2fd' : '#f1f8e9'); // Blue/green
const borderColor = isDuckMessage ? '#ff9800' : (isIncoming ? '#42a5f5' : '#66bb6a');
```

## Token Budgets & Sikkerhet

### Daily Limits (DuckMessenger)

```python
MAX_DAILY_INITIATED = 10      # Max meldinger initiert per dag
MAX_DAILY_TOTAL = 20           # Max totale meldinger per dag  
MAX_TOKENS_PER_MESSAGE = 500   # Max tokens per melding
COOLDOWN_HOURS = 2             # Timer mellom initiering
BOREDOM_THRESHOLD = 4.5        # Kedsomhet for auto-initering
```

### Loop Detection

**Similarity threshold:** 90% likhet mellom meldinger = loop

**Rapid messaging:** 5+ meldinger på <10 min = loop

**Database tracking:** Alle meldinger logges for analyse

### Når kan ender initiere?

✅ **TILLATT:**
- Bruker ber eksplisitt: "si hei til Seven"
- Kedsomhet > 4.5 OG ingen human-interaksjon siste 6 timer
- Har mottatt melding (kan svare)
- Spesiell event (maks 1 gang)

❌ **IKKE TILLATT:**
- Under samtale med menneske
- Allerede initiert 1 gang i dag
- Mindre enn 2 timer siden siste initiering
- Daglig limit nådd

## Fordeler

✅ **Gratis** - Ingen SMS-kostnad
✅ **Rask** - Direkte HTTP, ingen SMS-forsinkelse
✅ **Fleksibel** - Kan sende mer data enn SMS (bilder, JSON, etc.)
✅ **Enkel** - Samme relay-server som håndterer SMS
✅ **Skalerbar** - Støtter ubegrenset antall ender

## Testing

### 1. Test send

```bash
curl -X POST https://sms-relay.duckberry.no/duck/send \
  -H "Content-Type: application/json" \
  -d '{
    "from_duck": "samantha",
    "to_duck": "seven",
    "message": "Test message!"
  }'
```

### 2. Test poll

```bash
curl https://sms-relay.duckberry.no/duck/poll/seven
```

### 3. Python test

```python
from src.duck_sms import SMSManager

sms = SMSManager()

# Send
sms.send_duck_message("seven", "Hello from Python!")

# Poll
messages = sms.poll_duck_messages()
print(messages)
```

## Feilsøking

### Messages går ikke fram

1. Sjekk at SMS Relay kjører:
   ```bash
   curl https://sms-relay.duckberry.no/health
   ```

2. Sjekk duck name i .env matcher lowercase:
   ```bash
   DUCK_NAME=Samantha  # blir "samantha" i kode
   ```

3. Sjekk logs i SMS Relay:
   ```bash
   # Azure App Service logs
   ```

### Polling fungerer ikke

1. Verifiser DUCK_NAME er riktig
2. Sjekk nettverkstilkobling
3. Sjekk timeout-innstillinger

## Setup Guide for Seven

### Steg 1: Kopier nye filer fra Samantha

```bash
# Kopier disse filene fra Samantha-duck branch:
- src/duck_messenger.py (NY)
- sms-relay/app.py (oppdatert)
```

### Steg 2: Oppdater eksisterende filer

**chatgpt_voice.py:**
- Legg til `duck_message_polling_loop()` funksjon (se linje 267)
- Start thread i `main()` (se linje 715)
- Legg til duck message announcement handling i main loop (se linje 960)

**src/duck_sms.py:**
- Legg til `send_duck_message()` metode
- Legg til `poll_duck_messages()` metode
- Legg til `get_duck_contacts()` metode
- Oppdater `__init__` med `sms_relay_url`

### Steg 3: Konfigurer .env

```bash
DUCK_NAME=Seven
SMS_RELAY_URL=https://sms-relay.duckberry.no
```

### Steg 4: Oppdater relasjoner

I `src/duck_messenger.py`, sett relasjon til Samantha:

```python
DUCK_RELATIONS = {
    'samantha': 'min søster Samantha',
    # ... andre ender
}
```

### Steg 5: Test

```bash
# Fra Samantha
python3 -c "
from src.duck_sms import SMSManager
sms = SMSManager()
print(sms.send_duck_message('seven', 'Hei Seven!'))
"

# Fra Seven - sjekk logs
sudo journalctl -u chatgpt-duck -f
# Skal vise: "🦆💬 Message from samantha: Hei Seven!"
```

### Steg 6: Restart Services

```bash
sudo systemctl restart chatgpt-duck
```

## Memory Integration

Duck messages lagres som vanlige messages i `duck_memory.db`:

```sql
-- Messages tabell
INSERT INTO messages (user_text, ai_response, user_name, metadata)
VALUES (
    '[Duck message from seven]: Hei!',
    'Hei Seven! Hvordan går det?',
    'seven',  -- user_name = from_duck
    '{"type": "duck_message", "from_duck": "seven"}'
);

-- Duck messages tracking tabell
CREATE TABLE duck_messages (
    id INTEGER PRIMARY KEY,
    from_duck TEXT NOT NULL,
    to_duck TEXT NOT NULL,
    message TEXT NOT NULL,
    direction TEXT NOT NULL,  -- 'sent' eller 'received'
    initiated BOOLEAN,
    tokens_used INTEGER,
    timestamp TEXT
);
```

## Audio Announcements

Når melding kommer, sier anden høyt:

```
"Jeg har fått en melding fra min søster Seven. Den sier: [melding]"
```

Format basert på relasjon i `DUCK_RELATIONS`:
- `'seven'` → "min søster Seven"
- `'samantha'` → "min søster Samantha"
- Ukjent → "and-vennen min [name]"

## Troubleshooting

### Messages kommer ikke fram

1. Sjekk SMS Relay: `curl https://sms-relay.duckberry.no/health`
2. Sjekk DUCK_NAME i .env: må være lowercase i kode
3. Test send: `curl -X POST https://sms-relay.duckberry.no/duck/send ...`
4. Test poll: `curl https://sms-relay.duckberry.no/duck/poll/seven`

### Loop detection trigger

- Sjekk similarity threshold (default 90%)
- Sjekk rapid message limit (5 på 10 min)
- Se logs: `sudo journalctl -u chatgpt-duck | grep "Loop"`

### Token limit reached

- Sjekk daily stats:
  ```python
  from src.duck_messenger import DuckMessenger
  m = DuckMessenger()
  print(m.get_daily_stats())
  ```
- Reset kun i database (ikke anbefalt i produksjon)

### Ingen audio announcement

- Sjekk at fil opprettes: `ls -la /tmp/duck_message_announcement.txt`
- Sjekk logs for speak errors
- Verifiser at main loop sjekker filen (linje 960+)

## Roadmap

- [x] Basic duck-to-duck messaging
- [x] Loop prevention
- [x] Token budget tracking
- [x] Memory integration
- [x] Audio announcements
- [ ] Persistent queue (database i stedet for in-memory)
- [ ] Read receipts
- [ ] Typing indicators
- [ ] Group chats (flere ender samtidig)
- [ ] End-to-end encryption
- [ ] Voice command: "send melding til Seven"
- [ ] Scheduled messages
- [ ] Message history API endpoint
