"""
Duck Configuration Constants
All configuration constants and file paths for the duck assistant.
"""

import os

# ============ File Paths ============
MESSAGE_FILE = "/tmp/duck_message.txt"
MODEL_CONFIG_FILE = "/tmp/duck_model.txt"
PERSONALITY_FILE = "/tmp/duck_personality.txt"
VOICE_FILE = "/tmp/duck_voice.txt"
BEAK_FILE = "/tmp/duck_beak.txt"
SPEED_FILE = "/tmp/duck_speed.txt"
VOLUME_FILE = "/tmp/duck_volume.txt"
AI_QUERY_FILE = "/tmp/duck_ai_query.txt"
AI_RESPONSE_FILE = "/tmp/duck_ai_response.txt"
MESSAGES_FILE = "/home/admog/Code/chatgpt-and/config/messages.json"
SONG_REQUEST_FILE = "/tmp/duck_song_request.txt"
SONG_STOP_FILE = "/tmp/duck_song_stop.txt"

# ============ AI Model Configuration ============
DEFAULT_MODEL = "gpt-4-turbo-2024-04-09"  # GPT-4.1 Mini - beste balanse mellom kvalitet, hastighet og kostnad

# Tilgjengelige AI-modeller (basert på testing av perspektiv-håndtering)
AVAILABLE_MODELS = {
    # GPT-4 serien - Anbefalt for produksjon
    "gpt-4-turbo-2024-04-09": {"name": "GPT-4.1 Mini", "accuracy": "50%", "latency": "0.87s", "cost": "lav"},
    "gpt-4": {"name": "GPT-4", "accuracy": "75%", "latency": "1.38s", "cost": "høy"},
    "gpt-4-turbo": {"name": "GPT-4.1", "accuracy": "50%", "latency": "1.40s", "cost": "middels"},
    
    # GPT-4o serien - Billig men dårlig for perspektiv
    "gpt-4o-mini": {"name": "GPT-4o Mini", "accuracy": "25%", "latency": "1.12s", "cost": "svært lav"},
    
    # GPT-3.5 - Rask men dårlig kvalitet
    "gpt-3.5-turbo": {"name": "GPT-3.5 Turbo", "accuracy": "25%", "latency": "0.81s", "cost": "svært lav"},
    
    # GPT-5 serien - Ikke anbefalt for perspektiv-oppgaver
    "gpt-5-turbo": {"name": "GPT-5.2", "accuracy": "50%", "latency": "1.34s", "cost": "svært høy"},
}

# Kommentar: GPT-4.1 Mini er standard fordi den gir 50% korrekthet på perspektiv-spørsmål
# (dobbelt så bra som GPT-3.5), med bare 60ms ekstra latency og rimelig pris.

DEFAULT_VOICE = "nb-NO-IselinNeural"

# ============ Audio Configuration ============
# Fade in/out lengde i millisekunder (for å redusere knepp ved start/slutt)
FADE_MS = 150  # 150ms fade in/out

# Nebb-synkronisering (juster for bedre timing)
BEAK_CHUNK_MS = 30  # Hvor ofte nebbet oppdateres (mindre = mer responsivt)
BEAK_PRE_START_MS = 0  # Start nebb før aplay (negativ = etter aplay starter)

# ============ Wake Word Configuration ============
PORCUPINE_ACCESS_KEY_ENV = "PORCUPINE_ACCESS_KEY"
WAKE_WORD_PATH = "/home/admog/Code/chatgpt-and/Quack-quack.ppn"

# ============ Azure Configuration ============
AZURE_SPEECH_KEY_ENV = "AZURE_SPEECH_KEY"
AZURE_SPEECH_REGION_ENV = "AZURE_SPEECH_REGION"

# ============ OpenAI Configuration ============
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# ============ Home Assistant Configuration ============
HA_TOKEN_ENV = "HA_TOKEN"
HA_URL_ENV = "HA_URL"
