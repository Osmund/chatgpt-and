"""
ChatGPT Duck - Main Orchestrator
Hovedfil som koordinerer alle moduler for stemmeassistenten.
"""

import time
import os
import sys
import signal
import atexit
import json
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# Duck moduler
from duck_beak import Beak, CLOSE_DEG, OPEN_DEG, TRIM_DEG, SERVO_CHANNEL
from rgb_duck import set_blue, off, blink_yellow_purple
from src.duck_config import MESSAGES_FILE
from src.duck_memory import MemoryManager
from src.duck_user_manager import UserManager
from src.duck_audio import speak
from src.duck_speech import wait_for_wake_word, recognize_speech_from_mic
from src.duck_music import play_song
from src.duck_conversation import check_ai_queries, ask_for_user_switch, is_conversation_ending
from src.duck_ai import chatgpt_query, generate_message_metadata

# Flush stdout umiddelbart slik at print vises i journalctl
sys.stdout.reconfigure(line_buffering=True)

# MAX98357A SD pin skal kobles til fast 3.3V (pin 1 eller 17)
print("MAX98357A SD pin skal være koblet til 3.3V - forsterker alltid på", flush=True)


def cleanup():
    """Cleanup-funksjon som slår av alle LED ved avslutning"""
    print("Slår av LED og rydder opp...", flush=True)
    from rgb_duck import stop_blink, off
    stop_blink()
    off()


# Registrer cleanup ved normal exit og ved signaler
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), sys.exit(0)))


def main():
    """Hovedloop for stemmeassistenten"""
    # Prøv å initialisere servo, men fortsett uten hvis den ikke finnes
    beak = None
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        print("Servo initialisert OK", flush=True)
    except Exception as e:
        print(f"Advarsel: Kunne ikke initialisere servo (fortsetter uten): {e}", flush=True)
        beak = None
    
    # Initialiser memory manager
    try:
        memory_manager = MemoryManager()
        print("✅ Memory system initialisert", flush=True)
    except Exception as e:
        print(f"⚠️ Memory system feilet (fortsetter uten): {e}", flush=True)
        memory_manager = None
    
    # Initialiser user manager
    try:
        user_manager = UserManager()
        current_user = user_manager.get_current_user()
        print(f"✅ User system initialisert - nåværende bruker: {current_user['display_name']} ({current_user['relation']})", flush=True)
    except Exception as e:
        print(f"⚠️ User system feilet (fortsetter uten): {e}", flush=True)
        user_manager = None
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"

    # Last meldinger fra konfigurasjonsfil
    messages_config = {}
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                messages_config = json.load(f)
                print("✅ Lastet meldinger fra messages.json", flush=True)
    except Exception as e:
        print(f"⚠️ Kunne ikke laste messages.json: {e}", flush=True)
    
    # Fallback til hardkodede meldinger hvis fil mangler
    if not messages_config:
        messages_config = {
            "startup_messages": {
                "with_network": "Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er {ip}. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!",
                "without_network": "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"
            },
            "conversation": {
                "greeting": "Hei på du, hva kan jeg hjelpe deg med?",
                "no_response_timeout": "Jeg hører deg ikke. Da venter jeg til du sier navnet mitt igjen.",
                "no_response_retry": "Beklager, jeg hørte ikke hva du sa. Prøv igjen."
            },
            "web_interface": {
                "start_conversation": "Hei på du, hva kan jeg hjelpe deg med?"
            }
        }

    # Start bakgrunnstråd for AI-queries fra kontrollpanelet
    import threading
    ai_thread = threading.Thread(target=check_ai_queries, args=(api_key, speech_config, beak, memory_manager, user_manager), daemon=True)
    ai_thread.start()
    print("AI-query tråd startet", flush=True)

    # Oppstartshilsen (ikke la en TTS-feil stoppe tjenesten ved boot)
    time.sleep(3)  # Vent litt lenger for at systemet skal være klart
    
    # Hent IP-adresse (prøv flere ganger)
    import socket
    ip_address = None
    for attempt in range(5):  # Prøv 5 ganger
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            if ip_address and ip_address != "127.0.0.1":
                break  # Vellykket, avslutt loop
        except:
            if attempt < 4:  # Ikke vent etter siste forsøk
                time.sleep(2)  # Vent 2 sekunder før neste forsøk
    
    if ip_address and ip_address != "127.0.0.1":
        greeting = messages_config['startup_messages']['with_network'].replace('{ip}', ip_address.replace('.', ' punkt '))
        print(f"Oppstartshilsen med IP: {ip_address}", flush=True)
    else:
        greeting = messages_config['startup_messages']['without_network']
        print("Oppstartshilsen uten IP (nettverk ikke klart)", flush=True)
    
    # Prøv å si oppstartshilsen flere ganger hvis TTS/nettverk ikke er klart
    greeting_success = False
    for greeting_attempt in range(3):  # Prøv opptil 3 ganger
        try:
            speak(greeting, speech_config, beak)
            print("Oppstartshilsen ferdig", flush=True)
            greeting_success = True
            break
        except Exception as e:
            print(f"Oppstartshilsen mislyktes (forsøk {greeting_attempt + 1}/3): {e}", flush=True)
            if greeting_attempt < 2:  # Ikke vent etter siste forsøk
                time.sleep(5)  # Vent 5 sekunder før neste forsøk
    
    if not greeting_success:
        print("Oppstartshilsen kunne ikke sies etter 3 forsøk - fortsetter uten hilsen", flush=True)
    
    print("Anda venter på wake word... (si 'quack quack')", flush=True)
    
    # Session tracking: Generer ny session_id ved hver samtale
    current_session_id = None
    session_start_time = None
    SESSION_TIMEOUT_MINUTES = 30
    
    while True:
        external_message = wait_for_wake_word()
        
        # Generer ny session_id for ny samtale
        # Session fortsetter hvis mindre enn 30 min siden siste melding
        if current_session_id and session_start_time:
            time_since_start = datetime.now() - session_start_time
            if time_since_start > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                print(f"📅 Session timeout ({SESSION_TIMEOUT_MINUTES} min) - starter ny session", flush=True)
                current_session_id = None
        
        if current_session_id is None:
            current_session_id = str(uuid.uuid4())
            session_start_time = datetime.now()
            print(f"🆕 Ny session: {current_session_id[:8]}...", flush=True)
        else:
            print(f"♻️  Fortsetter session: {current_session_id[:8]}...", flush=True)
        
        # Sjekk timeout før ny samtale
        if user_manager:
            try:
                # Hent siste melding tidspunkt fra database
                last_message_time = None
                if memory_manager:
                    conn = memory_manager._get_connection()
                    c = conn.cursor()
                    c.execute("SELECT timestamp FROM messages ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    if row:
                        last_message_time = datetime.fromisoformat(row['timestamp'])
                    conn.close()
                
                # Sjekk om timeout skal trigges
                if user_manager.check_timeout(last_message_time):
                    current_user = user_manager.get_current_user()
                    print(f"⏰ Timeout for {current_user['display_name']} - bytter til Osmund", flush=True)
                    
                    # Bytt til Osmund
                    user_manager.switch_user('Osmund', 'Osmund', 'owner')
                    
                    # Si beskjed til Osmund
                    speak("Hei Osmund, jeg har byttet tilbake til deg etter timeout.", speech_config, beak)
            except Exception as e:
                print(f"⚠️ Feil ved timeout-sjekk: {e}", flush=True)
        
        # Hvis det er en ekstern melding, sjekk type
        if external_message:
            if external_message == '__START_CONVERSATION__':
                # Start samtale direkte med en kort hilsen
                print("Starter samtale via web-interface", flush=True)
                greeting_msg = messages_config['web_interface']['start_conversation']
                
                # Hent nåværende bruker fra user_manager
                if user_manager:
                    current_user = user_manager.get_current_user()
                    user_name = current_user['display_name']
                    greeting_msg = greeting_msg.replace('{name}', user_name)
                else:
                    greeting_msg = greeting_msg.replace('{name}', 'på du')
                
                speak(greeting_msg, speech_config, beak)
            elif external_message.startswith('__PLAY_SONG__'):
                # Spill av en sang
                song_path = external_message.replace('__PLAY_SONG__', '', 1)
                play_song(song_path, beak, speech_config)
                continue  # Gå tilbake til wake word etter sang
            else:
                # Bare si meldingen og gå tilbake til wake word
                speak(external_message, speech_config, beak)
                continue
        else:
            # Normal wake word - si hilsen
            greeting_msg = messages_config['conversation']['greeting']
            
            # Hent nåværende bruker fra user_manager
            if user_manager:
                current_user = user_manager.get_current_user()
                user_name = current_user['display_name']
                greeting_msg = greeting_msg.replace('{name}', user_name)
            else:
                greeting_msg = greeting_msg.replace('{name}', 'på du')
            
            speak(greeting_msg, speech_config, beak)
        
        # Start samtale (enten fra wake word eller samtale-trigger)
        messages = []
        no_response_count = 0  # Teller antall ganger uten svar
        
        while True:
            prompt = recognize_speech_from_mic()
            if not prompt:
                no_response_count += 1
                if no_response_count >= 2:
                    speak(messages_config['conversation']['no_response_timeout'], speech_config, beak)
                    break
                speak(messages_config['conversation']['no_response_retry'], speech_config, beak)
                continue
            
            # Reset teller når vi får svar
            no_response_count = 0
            
            # Sjekk om bruker vil avslutte samtalen
            should_end_conversation = is_conversation_ending(prompt)
            
            # Sjekk for direkte bytte til eier/Osmund
            prompt_lower = prompt.strip().lower()
            if user_manager and ("bytt til eier" in prompt_lower or "bytte til eier" in prompt_lower or 
                                  "bytt til osmund" in prompt_lower or "bytte til osmund" in prompt_lower):
                current_user = user_manager.get_current_user()
                if current_user['username'] != 'Osmund':
                    user_manager.switch_user('Osmund', 'Osmund', 'owner')
                    speak("Velkommen tilbake Osmund!", speech_config, beak)
                    print(f"✅ Byttet tilbake til eier: Osmund", flush=True)
                    break  # Start ny samtale
                else:
                    speak("Du er allerede Osmund, eieren!", speech_config, beak)
                    continue
            
            # Sjekk for brukerbytte-kommando
            if user_manager and ("bytt bruker" in prompt_lower or "skifte bruker" in prompt_lower or "bytte bruker" in prompt_lower):
                if ask_for_user_switch(speech_config, beak, user_manager):
                    # Vellykket brukerbytte - start ny samtale
                    break
                else:
                    # Mislykket - fortsett samtale
                    continue
            
            messages.append({"role": "user", "content": prompt})
            try:
                blink_yellow_purple()  # Start blinkende gul LED under tenkepause
                result = chatgpt_query(messages, api_key, memory_manager=memory_manager, user_manager=user_manager)
                off()  # Slå av blinking når svaret er klart
                
                # Håndter tuple-retur (svar, is_thank_you)
                if isinstance(result, tuple):
                    reply, is_thank_you = result
                else:
                    reply = result
                    is_thank_you = False
                
                # Sjekk om AI har markert samtalen som ferdig
                reply_upper = reply.upper()
                ai_wants_to_end = "[AVSLUTT]" in reply_upper or " AVSLUTT" in reply_upper or reply_upper.endswith("AVSLUTT")
                
                # Fjern AVSLUTT markør før TTS
                import re
                reply_for_speech = re.sub(r'\[?AVSLUTT\]?\.?', '', reply, flags=re.IGNORECASE).strip()
                reply_for_speech = ' '.join(reply_for_speech.split())
                
                print("ChatGPT svar:", reply_for_speech, flush=True)
                if ai_wants_to_end:
                    print("🔚 AI detekterte samtale-avslutning", flush=True)
                
                speak(reply_for_speech, speech_config, beak)
                messages.append({"role": "assistant", "content": reply_for_speech})
                
                # Lagre melding til memory database
                if memory_manager and user_manager:
                    try:
                        current_user = user_manager.get_current_user()
                        
                        # Generer metadata for meldingen
                        msg_metadata = generate_message_metadata(prompt, reply_for_speech)
                        metadata_json = json.dumps(msg_metadata, ensure_ascii=False)
                        
                        memory_manager.save_message(
                            prompt, 
                            reply_for_speech, 
                            session_id=current_session_id, 
                            user_name=current_user['username'],
                            metadata=metadata_json
                        )
                        
                        # Oppdater aktivitet og message count
                        user_manager.update_activity()
                        user_manager.increment_message_count(current_user['username'])
                    except Exception as e:
                        print(f"⚠️ Kunne ikke lagre melding: {e}", flush=True)
                
                # Sjekk om samtalen skal avsluttes
                if ai_wants_to_end:
                    print("🔚 Samtale avsluttet av AI", flush=True)
                    break
                elif should_end_conversation:
                    print("🔚 Samtale avsluttet (bruker sa avslutningsfrase)", flush=True)
                    break
                elif is_thank_you:
                    print("🔚 Samtale avsluttet (bruker takket)", flush=True)
                    break
            except Exception as e:
                off()
                print("Feil:", e)
                speak("Beklager, det oppstod en feil.", speech_config, beak)
            
            set_blue()  # Blå LED = klar for neste input


if __name__ == "__main__":
    main()
