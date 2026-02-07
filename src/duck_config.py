"""
Duck Configuration Constants
All configuration constants and file paths for the duck assistant.
"""

import os

# ============ Base Path ============
# Automatically detect the project root directory
# src/duck_config.py -> go up one level to get project root
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
MESSAGES_FILE = os.path.join(BASE_PATH, "config", "messages.json")
SONG_REQUEST_FILE = "/tmp/duck_song_request.txt"
SONG_STOP_FILE = "/tmp/duck_song_stop.txt"

# Config directory paths
CONFIG_DIR = os.path.join(BASE_PATH, "config")
LOCATIONS_FILE = os.path.join(CONFIG_DIR, "locations.json")
PERSONALITIES_FILE = os.path.join(CONFIG_DIR, "personalities.json")
SAMANTHA_IDENTITY_FILE = os.path.join(CONFIG_DIR, "samantha_identity.json")

# Database path
DB_PATH = os.path.join(BASE_PATH, "duck_memory.db")

# Wake word path
WAKE_WORD_PATH = os.path.join(BASE_PATH, "Quack-quack.ppn")

# ============ AI Model Configuration ============
# Les fra .env, fallback til gpt-4.1-mini
DEFAULT_MODEL = os.getenv("AI_MODEL_CHAT", "gpt-4.1-mini-2025-04-14")

# Tilgjengelige AI-modeller (basert på testing av perspektiv-håndtering)
AVAILABLE_MODELS = {
    # GPT-4.1 serien - Anbefalt (nyeste 2025)
    "gpt-4.1-mini-2025-04-14": {"name": "GPT-4.1 Mini", "accuracy": "50%", "latency": "0.70s", "cost": "lav"},
    
    # GPT-4 serien - Eldre modeller
    "gpt-4-turbo-2024-04-09": {"name": "GPT-4 Turbo (2024)", "accuracy": "50%", "latency": "0.87s", "cost": "middels"},
    "gpt-4": {"name": "GPT-4", "accuracy": "75%", "latency": "1.38s", "cost": "høy"},
    "gpt-4-turbo": {"name": "GPT-4.1", "accuracy": "50%", "latency": "1.40s", "cost": "middels"},
    
    # GPT-4o serien - Billig, god for SMS
    "gpt-4o-mini": {"name": "GPT-4o Mini", "accuracy": "25%", "latency": "1.12s", "cost": "svært lav"},
    
    # GPT-3.5 - Rask men dårlig kvalitet
    "gpt-3.5-turbo": {"name": "GPT-3.5 Turbo", "accuracy": "25%", "latency": "0.81s", "cost": "svært lav"},
    
    # GPT-5 serien - Ikke anbefalt for perspektiv-oppgaver
    "gpt-5-turbo": {"name": "GPT-5.2", "accuracy": "50%", "latency": "1.34s", "cost": "svært høy"},
}

# Kommentar: GPT-4.1 Mini (2025) er standard fordi den gir 50% korrekthet på perspektiv-spørsmål,
# er nyeste generasjon (april 2025), har lavest latency (~0.70s), og er 10x billigere enn GPT-4 Turbo.

DEFAULT_VOICE = "nb-NO-IselinNeural"

# ============ Audio Configuration ============
# Fade in/out lengde i millisekunder (for å redusere knepp ved start/slutt)
FADE_MS = 150  # 150ms fade in/out

# Nebb-synkronisering (juster for bedre timing)
BEAK_CHUNK_MS = 30  # Hvor ofte nebbet oppdateres (mindre = mer responsivt)
BEAK_PRE_START_MS = 0  # Start nebb før aplay (negativ = etter aplay starter)

# Music directory
MUSIKK_DIR = os.path.join(BASE_PATH, "musikk")

# ============ Porcupine Configuration ============
PORCUPINE_ACCESS_KEY_ENV = "PORCUPINE_ACCESS_KEY"
# WAKE_WORD_PATH is already defined above using BASE_PATH (line 40)

# ============ Azure Configuration ============
AZURE_SPEECH_KEY_ENV = "AZURE_SPEECH_KEY"
AZURE_SPEECH_REGION_ENV = "AZURE_SPEECH_REGION"

# ============ OpenAI Configuration ============
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# ============ Home Assistant Configuration ============
HA_TOKEN_ENV = "HA_TOKEN"
HA_URL_ENV = "HA_URL"

# ============ Memory System Configuration ============
# Hvor mange facts embedding-søk skal returnere
MEMORY_EMBEDDING_SEARCH_LIMIT = 30

# Hvor mange minner som skal inkluderes i kontekst
MEMORY_LIMIT = 8

# Similarity threshold for minner (0.0-1.0, lavere = mer inkluderende)
MEMORY_THRESHOLD = 0.35

# Hvor mange frekvente facts som legges til hvis embedding finner få
MEMORY_FREQUENT_FACTS_LIMIT = 15

# Minimum antall expanded facts før frequent facts legges til
MEMORY_EXPAND_THRESHOLD = 15
