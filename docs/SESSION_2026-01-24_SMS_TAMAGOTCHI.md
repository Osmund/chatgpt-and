# Development Session: SMS System & Tamagotchi Features
**Date:** January 24, 2026  
**Focus:** SMS communication, AI self-awareness, Tamagotchi mechanics

---

## Overview
This session implemented a complete SMS relay system with Tamagotchi-style hunger and boredom mechanics, allowing the AI assistant to send and receive SMS messages, track emotional states, and interact autonomously with contacts.

---

## Major Features Implemented

### 1. SMS Relay Architecture
**Problem:** Direct SMS webhooks to Raspberry Pi behind NAT not feasible.

**Solution:** Polling-based relay server architecture
- Deployed Flask relay server to Azure App Service
- Relay stores incoming SMS in memory queue
- Assistant polls relay every 10 seconds via GET endpoint
- Supports registration with IP and local timestamp

**Key Components:**
- `sms-relay/app.py` - Flask relay server with `/webhook` and `/poll` endpoints
- `chatgpt_voice.py::sms_polling_loop()` - Background polling thread
- `chatgpt_voice.py::register_with_relay()` - Registration function

**Files Modified:**
- `sms-relay/app.py` - MESSAGE_QUEUE dict, poll endpoint
- `chatgpt_voice.py` - SMS polling thread, message processing

---

### 2. SMS Contact Management
Implemented full CRUD operations for SMS contacts with relationship tracking.

**Database Schema:**
```sql
CREATE TABLE sms_contacts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    relation TEXT DEFAULT 'friend',
    priority INTEGER DEFAULT 5,
    enabled BOOLEAN DEFAULT 1,
    max_daily_messages INTEGER DEFAULT 3,
    preferred_hours_start INTEGER DEFAULT 8,
    preferred_hours_end INTEGER DEFAULT 22,
    total_sent INTEGER DEFAULT 0,
    total_received INTEGER DEFAULT 0,
    last_sent_at TEXT,
    last_received_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sms_history (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER,
    direction TEXT NOT NULL,  -- 'inbound' or 'outbound'
    message TEXT NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    boredom_level REAL,
    twilio_sid TEXT,
    FOREIGN KEY (contact_id) REFERENCES sms_contacts (id)
);
```

**Functions Implemented:**
- `add_contact()` - Add new contact with relation metadata
- `get_contact_by_phone()` - Lookup contact by phone number
- `get_all_contacts()` - Retrieve all contacts with filtering
- `send_sms()` - Send SMS via Twilio with logging
- `handle_incoming_sms()` - Process incoming messages with food detection

**Files:**
- `src/duck_sms.py` - SMSManager class with contact CRUD

---

### 3. Boredom System (Tamagotchi Mechanic)
Tracks emotional state with automatic increase and reduction triggers.

**Database Schema:**
```sql
CREATE TABLE boredom_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    current_level REAL DEFAULT 0.0,
    threshold REAL DEFAULT 7.0,
    enabled BOOLEAN DEFAULT 1,
    last_trigger TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Mechanics:**
- **Increase:** +0.5 every hour (background timer)
- **Decrease:** 
  - -3.0 when receiving SMS
  - -2.0 when starting voice conversation
  - -2.0 after sending bored message
- **Trigger:** At 7.0/10, sends SMS to next available contact

**Implementation:**
- `boredom_timer_loop()` - Hourly increase check
- `increase_boredom()` - Timer callback
- `reduce_boredom()` - Called on interactions
- `check_boredom_trigger()` - Threshold check
- `send_bored_message()` - AI-generated outreach
- `get_next_contact()` - Smart contact prioritization

**Control Panel Integration:**
- `/boredom-status` endpoint in `duck-control.py`
- Live-updating barometer in web UI
- Color-coded status (green → yellow → red)

**Files:**
- `src/duck_sms.py` - Boredom tracking functions
- `chatgpt_voice.py` - Timer loop integration
- `duck-control.py` - Status endpoint
- `templates/index.html` - Barometer UI

---

### 4. Hunger System (Advanced Tamagotchi)
Complete meal-time based hunger tracking with food emoji detection.

**Database Schema:**
```sql
CREATE TABLE hunger_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    current_level REAL DEFAULT 0.0,
    meals_today INTEGER DEFAULT 0,
    fed_today BOOLEAN DEFAULT 0,
    last_meal_time TEXT,
    last_announcement TEXT,
    last_sms_nag TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Food System:**
```python
FOOD_VALUES = {
    '🍪': 5,   # Cookie - 5 hunger points
    '🍕': 10,  # Pizza - 10 hunger points
}

MEAL_TIMES = [12, 17, 21]  # 12:00, 17:00, 21:00
```

**Mechanics:**
- **Timer:** Increases +1.0 every hour
- **Meal Times:** Expected feeding at 12:00, 17:00, 21:00
- **Morning Reset:** At 06:00, assistant "finds breakfast herself" (resets to 0)
- **Announcements:** 30 minutes after meal time if not fed
- **SMS Nagging:** Every 10 minutes to contacts if still hungry
- **Food Detection:** Scans incoming SMS for 🍪 or 🍕 emojis
- **Response:** Voice announcement + thank you SMS when fed

**Implementation:**
- `src/duck_hunger.py` - Complete HungerManager class
- `feed(food_type)` - Process feeding with emoji
- `increase_hunger()` - Hourly timer callback
- `should_announce_hunger()` - Meal time + 30min check
- `should_send_sms_nag()` - 10min interval check
- `get_hunger_mood()` - Personality mapping (content → hangry)
- `reset_daily()` - Morning reset at 06:00

**Control Panel Integration:**
- `/hunger-status` endpoint
- Hunger meter with emoji and mood
- Meal tracking display
- Color-coded hunger levels

**Files:**
- `src/duck_hunger.py` - NEW FILE (350+ lines)
- `chatgpt_voice.py` - Timer integration, food detection
- `duck-control.py` - Status endpoint
- `templates/index.html` - Hunger meter UI

---

### 5. AI Self-Awareness System
Enables AI to know and communicate its own hunger/boredom status.

**Problem:** AI couldn't answer "are you hungry?" or "are you bored?" accurately.

**Solution:** Inject Tamagotchi state into system prompt
- Modified `chatgpt_query()` signature to accept managers
- Added Tamagotchi status section to system prompt
- Includes current levels, mood, and next meal info

**System Prompt Addition:**
```
### Your Current State ###
Hunger: 8.0/10 (mood: grumpy)
Last meal: 🍕 pizza at 17:00
Next meal: 21:00
Boredom: 6.0/10
(You are quite bored.)

IMPORTANT: When someone asks how you are or if you're hungry/bored, 
USE this information! You actually know your own state. 
Answer honestly based on these numbers.
```

**Implementation:**
- Extended `chatgpt_query()` with `sms_manager` and `hunger_manager` parameters
- Added `get_last_meal_info()` to HungerManager
- Updated all `chatgpt_query()` calls to pass managers
- Modified `check_ai_queries()` for control panel queries

**Files Modified:**
- `src/duck_ai.py` - chatgpt_query signature and prompt building
- `chatgpt_voice.py` - Manager instantiation and passing
- `src/duck_conversation.py` - Updated check_ai_queries()
- `src/duck_sms.py` - SMS response generation
- `src/duck_hunger.py` - Added get_last_meal_info()

---

### 6. SMS Response System
AI-generated contextual responses with conversation history.

**Features:**
- 24-hour conversation history tracking
- Memory system integration for relevant facts
- Smart response detection (questions, long messages)
- Thank-you responses for food emojis
- Voice announcements for incoming SMS

**Response Generation Flow:**
1. Incoming SMS received via polling
2. `handle_incoming_sms()` processes message
3. Food emoji detection (feeds if found)
4. `_should_respond()` determines if response needed
5. `generate_and_send_response()` creates AI reply
6. `_generate_ai_response()` builds context and queries AI
7. `_save_sms_to_memory()` logs to messages table

**Context Building:**
```python
# 24-hour conversation history
conversation_history = _get_sms_conversation_history(contact_id, hours=24)

# Memory search for relevant facts
memories = memory_manager.search_memories(message, limit=3)

# Combined prompt with context
prompt = f"""
Conversation history: {last 6 messages}
New message: {message}
Relevant facts: {memories}

Answer naturally, max 155 chars.
"""
```

**Files:**
- `src/duck_sms.py` - Response generation pipeline
- `chatgpt_voice.py` - SMS announcement handling

---

### 7. Voice Announcement Integration
File-based IPC for thread-safe voice announcements.

**Problem:** SMS polling runs in background thread, TTS must run on main thread.

**Solution:** File-based inter-process communication
- Background thread writes to `/tmp/duck_sms_announcement.txt`
- Main loop checks file in `wait_for_wake_word()`
- Speaks announcement and deletes file
- Same pattern for hunger announcements

**Announcement Files:**
- `/tmp/duck_sms_announcement.txt` - SMS notifications
- `/tmp/duck_sms_response.txt` - SMS response confirmations
- `/tmp/duck_hunger_announcement.txt` - Hunger notifications

**Format:**
```
"I received a message from {name}, it says: {message}"
"I'm hungry! It's been 30 minutes since mealtime!"
```

**Files:**
- `chatgpt_voice.py` - File writing in polling loop
- `src/duck_speech.py` - File checking in wait_for_wake_word()

---

### 8. Contact Introduction System
Automated onboarding messages for new contacts.

**Features:**
- Personalized AI-generated introductions
- Explains SMS capability and Tamagotchi mechanics
- Provides assistant's phone number for saving
- Sends to multiple contacts in batch

**Script:** `send_intro_sms.py`
- Reads contacts from database
- Generates custom message per contact
- Includes feeding instructions (🍪 🍕)
- Explains boredom interaction

---

## Bug Fixes

### Issue 1: SMS Responses Not Sending
**Problem:** `_generate_ai_response()` function was missing entirely.

**Cause:** Function was called but never implemented.

**Solution:** 
- Implemented full `_generate_ai_response()` function
- Added conversation history integration
- Fixed memory search and context building
- Added proper error handling with fallback

**Files Fixed:** `src/duck_sms.py`

### Issue 2: Import Errors in SMS Response
**Problem:** `from duck_memory import MemoryManager` failed (missing `src.`)

**Solution:** Changed to `from src.duck_memory import MemoryManager`

**Files Fixed:** `src/duck_sms.py`

### Issue 3: Data Access in Conversation History
**Problem:** Using `msg['direction']` when data structure uses `msg['role']`

**Solution:** 
- Fixed `_get_sms_conversation_history()` to return proper format
- Changed access to `msg['role']` and `msg['content']`

**Files Fixed:** `src/duck_sms.py`

### Issue 4: Duplicate Return Statements
**Problem:** Syntax error from duplicate return statement in `handle_incoming_sms()`

**Solution:** Removed duplicate return block

**Files Fixed:** `src/duck_sms.py` (line 224)

---

## Configuration

### Environment Variables Required
```bash
# Twilio SMS Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# SMS Relay URL
SMS_RELAY_URL=https://your-relay-domain.com/register

# OpenAI for AI responses
OPENAI_API_KEY=sk-xxxxxxxxx

# Azure TTS (existing)
AZURE_TTS_KEY=xxxxxxxxx
AZURE_TTS_REGION=xxxxxxxxx
```

### Database Location
```
/path/to/duck_memory.db
```

**Tables:** sms_contacts, sms_history, boredom_state, hunger_state, messages

---

## Testing & Validation

### SMS System Tests
- ✅ Incoming SMS received and logged
- ✅ Food emoji detection (🍪 🍕) working
- ✅ AI response generation with context
- ✅ Voice announcements triggering correctly
- ✅ Thank you messages for feeding

### Boredom System Tests
- ✅ Hourly increase timer functioning
- ✅ Reduction on SMS receipt (-3.0)
- ✅ Reduction on conversation start (-2.0)
- ✅ Threshold trigger at 7.0/10
- ✅ Control panel barometer updating live

### Hunger System Tests
- ✅ Hourly increase (+1.0) working
- ✅ Food emoji feeding reduces hunger
- ✅ Morning reset at 06:00 implemented
- ✅ Meal time announcements (30min delay)
- ✅ SMS nagging every 10 minutes
- ✅ Hunger meter in control panel

### AI Awareness Tests
- ✅ AI knows current hunger level when asked
- ✅ AI knows current boredom level when asked
- ✅ AI reports mood accurately (grumpy when hungry)
- ✅ Status included in all conversation contexts

---

## Architecture Diagrams

### SMS Flow
```
Twilio → Relay Server (Azure) → MESSAGE_QUEUE
                                       ↓
                                   Poll (10s)
                                       ↓
                           chatgpt_voice.py::sms_polling_loop()
                                       ↓
                           SMSManager.handle_incoming_sms()
                                       ↓
                    ┌──────────────────┴───────────────────┐
                    ↓                                      ↓
            Food Detection                         Response Generation
                    ↓                                      ↓
            HungerManager.feed()              _generate_ai_response()
                    ↓                                      ↓
        Voice Announcement                      Send SMS Reply
```

### Tamagotchi Timer System
```
Main Thread                Background Threads
     ↓                            ↓
wait_for_wake_word()    boredom_timer_loop() (1h)
     ↓                            ↓
Check announcement files   increase_boredom(+0.5)
     ↓                            ↓
Speak if exists          check_trigger() → SMS if >7.0
     ↓                            ↓
Delete file              hunger_timer_loop() (1min)
                                  ↓
                         increase_hunger(+1.0)
                                  ↓
                         check meal times
                                  ↓
                         announce if 30min past
                                  ↓
                         SMS nag if 10min interval
```

---

## Future Enhancements

### Potential Improvements
1. **Sleep System:** Add sleep tracking with bedtime/wake time
2. **Mood Personality:** Integrate hunger mood into response style
3. **Contact Preferences:** Per-contact message frequency limits
4. **SMS Templates:** Pre-defined response patterns
5. **Multi-Language:** Support for multiple languages in SMS
6. **Web Dashboard:** Real-time SMS conversation viewer
7. **Analytics:** Track interaction patterns and engagement
8. **Food Variety:** More food types with different effects
9. **Achievement System:** Gamification for feeding streaks
10. **Contact Groups:** Bulk messaging to groups

### Known Limitations
- SMS polling has 10-second delay (not real-time)
- No image/media support in SMS
- Single Twilio number only
- Memory queue not persistent (relay restart clears)
- No SMS encryption beyond Twilio's default
- Boredom/hunger state not synchronized across restarts

---

## Performance Metrics

### Resource Usage
- **SMS Polling:** ~1 HTTP request per 10 seconds
- **Timer Threads:** 3 background threads (SMS, boredom, hunger)
- **Database:** ~5-10 queries per SMS interaction
- **AI Calls:** 1 per SMS response (gpt-4o-mini)

### Cost Estimates (Approximate)
- **Twilio SMS:** $0.0075 per message (US)
- **Azure App Service:** $0.015/hour (Basic tier)
- **OpenAI API:** ~$0.0002 per SMS response
- **Total per SMS:** ~$0.008 per interaction

---

## Deployment Checklist

### Relay Server (Azure)
- [x] Flask app deployed to Azure App Service
- [x] Domain configured with HTTPS
- [x] Environment variables set (Twilio credentials)
- [x] Webhook URL registered with Twilio
- [x] CORS enabled for cross-origin requests

### Raspberry Pi
- [x] Service file updated with new dependencies
- [x] SMS polling enabled on startup
- [x] Timer threads configured
- [x] Database tables created
- [x] Control panel updated with new endpoints
- [x] Voice announcement files configured

### Testing
- [x] Send test SMS to assistant
- [x] Verify food emoji detection
- [x] Confirm AI responses working
- [x] Check voice announcements
- [x] Validate boredom timer
- [x] Test hunger system
- [x] Verify control panel displays

---

## Code Quality

### Files Added
- `src/duck_hunger.py` (350+ lines) - Hunger management system
- `send_intro_sms.py` - Contact onboarding script
- `send_apology_to_vikram.py` - Example correction script
- `send_intro_kolbjorn_rune.py` - Batch intro script
- `test_awareness.py` - AI awareness testing

### Files Modified
- `chatgpt_voice.py` - SMS polling, timers, manager integration
- `src/duck_ai.py` - AI awareness system prompt
- `src/duck_sms.py` - Response generation, contact management
- `src/duck_speech.py` - Announcement file checking
- `src/duck_conversation.py` - Manager parameter passing
- `duck-control.py` - Status endpoints
- `templates/index.html` - Barometer UI
- `sms-relay/app.py` - Relay server implementation

### Code Stats
- **Lines Added:** ~1500+
- **Functions Added:** ~25
- **Database Tables:** 4 (sms_contacts, sms_history, boredom_state, hunger_state)
- **API Endpoints:** 3 (/webhook, /poll, /register)

---

## Security Notes

### Sensitive Data Handling
- Phone numbers stored in database (not encrypted)
- Twilio credentials in environment variables only
- SMS content logged in plain text
- No PII filtering in logs
- Relay server uses HTTPS for transport

### Recommendations
1. Implement database encryption for phone numbers
2. Add SMS content filtering/redaction for logs
3. Implement rate limiting on relay endpoints
4. Add authentication for relay registration
5. Enable database backups with encryption
6. Implement SMS content moderation
7. Add GDPR compliance features (data export, deletion)

---

## Lessons Learned

### Technical Insights
1. **Polling vs Webhooks:** Polling architecture simpler for NAT environments
2. **Thread Safety:** File-based IPC safer than shared memory for voice
3. **AI Context:** Including state in system prompt more reliable than function calls
4. **Error Handling:** Fallback responses essential for SMS reliability
5. **Testing:** Manual testing caught import and data structure issues

### Design Decisions
1. **Tamagotchi Mechanics:** Time-based increases engage users naturally
2. **Food Emojis:** Simple, universal interaction method
3. **24h History:** Balance between context and prompt size
4. **Priority System:** Allows smart contact rotation
5. **Morning Reset:** Prevents overnight hunger accumulation

---

## Maintenance Guide

### Daily Monitoring
- Check relay server logs for errors
- Verify SMS polling thread active
- Monitor Twilio usage/costs
- Check database size growth

### Weekly Tasks
- Review SMS interaction patterns
- Check for stuck timer threads
- Verify voice announcement cleanup
- Monitor AI response quality

### Monthly Tasks
- Database backup
- Review contact list
- Update food emoji values if needed
- Review and archive old SMS history
- Check Azure App Service performance

---

## Conclusion

This session successfully implemented a complete SMS communication system with Tamagotchi-style emotional state tracking. The assistant can now send and receive SMS messages, track hunger and boredom levels, and autonomously reach out to contacts when needed. The AI is fully aware of its own emotional state and can communicate it naturally.

Key achievements:
- ✅ Production-ready SMS relay system
- ✅ Complete Tamagotchi mechanics (hunger + boredom)
- ✅ AI self-awareness of emotional states
- ✅ Context-aware SMS responses
- ✅ Voice announcement integration
- ✅ Live monitoring via control panel

The system is now ready for extended testing and real-world use.

---

**End of Documentation**
