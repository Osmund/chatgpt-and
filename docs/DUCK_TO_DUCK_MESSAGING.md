# Duck-to-Duck Messaging

Ender kan sende meldinger til hverandre via SMS Relay uten SMS-kostnad.

## Oversikt

**Problem:** SMS koster penger, og ender burde kunne snakke sammen gratis.

**Løsning:** Duck-to-duck messaging via SMS Relay server - direkte HTTP kommunikasjon.

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

## Python API (duck_sms.py)

### Send melding til annen and

```python
from src.duck_sms import SMSManager

sms = SMSManager()

# Send message to Seven
result = sms.send_duck_message(
    to_duck="seven",
    message="Hei Seven! Hvordan går det?",
    media_url=None  # optional
)

print(result)
# {'status': 'sent', 'to': 'seven'}
```

### Poll for meldinger fra andre ender

```python
messages = sms.poll_duck_messages()

for msg in messages:
    print(f"From {msg['from_duck']}: {msg['message']}")
    # From samantha: Hei Seven! Hvordan går det?
```

### Liste over andre ender

```python
other_ducks = sms.get_duck_contacts()
# ['seven'] (hvis self er samantha)
```

## Integrering i Chatbot

### 1. Polling i bakgrunnen

Legg til polling i main loop (chatgpt_voice.py):

```python
import threading
import time

def poll_duck_messages_background(sms_manager, services):
    """Background thread for polling duck messages"""
    while True:
        try:
            messages = sms_manager.poll_duck_messages()
            
            for msg in messages:
                # Process duck message
                from_duck = msg['from_duck']
                message_text = msg['message']
                
                print(f"🦆💬 Message from {from_duck}: {message_text}")
                
                # Generate AI response
                from src.duck_ai import chatgpt_query
                
                prompt = f"""Du fikk nettopp en melding fra {from_duck} (en annen and):
"{message_text}"

Skriv et kort, hyggelig svar. Dere er and-venner som bor hos forskjellige folk.
Hold det kort og personlig."""
                
                response = chatgpt_query(
                    messages=[{"role": "user", "content": prompt}],
                    api_key=os.getenv('OPENAI_API_KEY'),
                    model='gpt-4o-mini',
                    sms_manager=sms_manager,
                    hunger_manager=services.get_hunger_manager(),
                    vision_service=services.get_vision_service()
                )
                
                if isinstance(response, tuple):
                    response = response[0]
                
                # Send reply
                sms_manager.send_duck_message(
                    to_duck=from_duck,
                    message=response.strip()
                )
        
        except Exception as e:
            print(f"⚠️ Duck polling error: {e}")
        
        time.sleep(5)  # Poll every 5 seconds

# Start background thread
poll_thread = threading.Thread(
    target=poll_duck_messages_background,
    args=(sms_manager, services),
    daemon=True
)
poll_thread.start()
```

### 2. Voice command for sending

Legg til tool i duck_tools.py:

```python
{
    "type": "function",
    "function": {
        "name": "send_duck_message",
        "description": "Send a message to another duck (Samantha or Seven) without using SMS",
        "parameters": {
            "type": "object",
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

## Konfigurasjon

### .env

```bash
# SMS Relay URL
SMS_RELAY_URL=https://sms-relay.duckberry.no

# Duck name (må matche i relay)
DUCK_NAME=Samantha  # eller "Seven"
```

### Flere ender

Oppdater `get_duck_contacts()` i duck_sms.py:

```python
def get_duck_contacts(self) -> List[str]:
    """Get list of other ducks"""
    all_ducks = ['samantha', 'seven', 'oslo-duck', 'another-duck']
    return [d for d in all_ducks if d.lower() != self.duck_name.lower()]
```

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

## Roadmap

- [ ] Persistent queue (database i stedet for in-memory)
- [ ] Message history/arkivering
- [ ] Read receipts
- [ ] Typing indicators
- [ ] Group chats (flere ender samtidig)
- [ ] End-to-end encryption
