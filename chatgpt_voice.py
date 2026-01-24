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
import threading
import socket
import requests
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
from src.adaptive_greetings import get_adaptive_greeting, get_adaptive_goodbye

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


def register_with_relay():
    """Register Duck with SMS relay server on startup"""
    relay_url = os.getenv('SMS_RELAY_URL', 'https://relay.duckberry.no/register')
    twilio_number = os.getenv('TWILIO_NUMBER')
    duck_name = os.getenv('DUCK_NAME', 'Duck-Oslo')
    
    if not twilio_number:
        print("⚠️ TWILIO_NUMBER not set - skipping SMS relay registration", flush=True)
        return
    
    try:
        # Get current IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        current_ip = s.getsockname()[0]
        s.close()
        
        # Register with relay
        response = requests.post(relay_url, json={
            'twilio_number': twilio_number,
            'name': duck_name,
            'ip': current_ip
        }, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Registered with SMS relay: {duck_name} at {current_ip}", flush=True)
            print(f"   Twilio number: {twilio_number}", flush=True)
        else:
            print(f"⚠️ Failed to register with SMS relay: {response.status_code} - {response.text}", flush=True)
    except Exception as e:
        print(f"⚠️ SMS relay registration failed: {e}", flush=True)


def sms_polling_loop():
    """Poll relay for new SMS messages every 10 seconds"""
    relay_url = os.getenv('SMS_RELAY_URL', 'https://sms-relay.duckberry.no/register')
    base_url = relay_url.replace('/register', '')
    twilio_number = os.getenv('TWILIO_NUMBER')
    
    if not twilio_number:
        print("⚠️ TWILIO_NUMBER not set - skipping SMS polling", flush=True)
        return
    
    # URL encode the number
    import urllib.parse
    encoded_number = urllib.parse.quote(twilio_number, safe='')
    poll_url = f"{base_url}/poll/{encoded_number}"
    
    while True:
        time.sleep(10)  # Poll every 10 seconds
        try:
            response = requests.get(poll_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                
                if messages:
                    print(f"📨 Received {len(messages)} SMS message(s)", flush=True)
                    
                    # Process each message
                    for msg in messages:
                        try:
                            from_number = msg.get('from')
                            message_text = msg.get('message')
                            
                            print(f"📱 SMS from {from_number}: {message_text[:50]}...", flush=True)
                            
                            # Forward to SMS handler
                            import sys
                            sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
                            from duck_sms import SMSManager
                            from duck_audio import speak
                            
                            sms_manager = SMSManager()
                            result = sms_manager.handle_incoming_sms(from_number, message_text)
                            
                            # Announce SMS with voice
                            if result.get('status') == 'ok':
                                contact = result.get('contact')
                                
                                # Always announce the incoming message first
                                if contact:
                                    contact_name = contact.get('name', from_number)
                                    announcement = f"Jeg fikk en melding fra {contact_name}, den sier: {message_text}"
                                else:
                                    announcement = f"Jeg fikk en melding fra {from_number}, den sier: {message_text}"
                                
                                print(f"🔊 Announcing SMS: {announcement[:50]}...", flush=True)
                                
                                # Write announcement to file for main loop to speak
                                with open('/tmp/duck_sms_announcement.txt', 'w', encoding='utf-8') as f:
                                    f.write(announcement)
                                
                                # Send AI-generated response (AI will know if she was fed from context)
                                if result.get('should_respond'):
                                    response_result = sms_manager.generate_and_send_response(
                                        contact, message_text
                                    )
                                    if response_result.get('status') == 'sent':
                                        response_text = response_result.get('message', '')
                                        print(f"📤 Sent response: {response_text[:50]}...", flush=True)
                                        # Write response announcement to file
                                        with open('/tmp/duck_sms_response.txt', 'w', encoding='utf-8') as f:
                                            f.write(f"Jeg sendte svar: {response_text}")
                            
                            print(f"✅ SMS processed", flush=True)
                        except Exception as msg_error:
                            print(f"⚠️ Error processing SMS: {msg_error}", flush=True)
        except Exception as e:
            print(f"⚠️ SMS polling error: {e}", flush=True)


def boredom_timer_loop():
    """Increase boredom gradually every hour and check for triggers"""
    import sys
    sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
    from duck_sms import SMSManager
    
    while True:
        time.sleep(3600)  # Every hour
        try:
            sms_manager = SMSManager()
            
            # Increase boredom
            new_level = sms_manager.increase_boredom(amount=0.5)
            
            # Check if threshold reached
            if sms_manager.check_boredom_trigger():
                print(f"🥱 Boredom threshold reached ({new_level:.1f}/10) - sending message", flush=True)
                result = sms_manager.send_bored_message()
                
                if result.get('status') == 'sent':
                    contact = result.get('contact')
                    message = result.get('message')
                    print(f"📤 Sent bored message to {contact['name']}: {message[:50]}...", flush=True)
                    
                    # Write announcement to file
                    announcement = f"Jeg sendte en melding til {contact['name']} fordi jeg kjeder meg."
                    with open('/tmp/duck_sms_announcement.txt', 'w', encoding='utf-8') as f:
                        f.write(announcement)
                elif result.get('status') == 'no_contact':
                    print("😔 Ingen kontakter tilgjengelig for kjed-melding", flush=True)
        except Exception as e:
            print(f"⚠️ Boredom timer error: {e}", flush=True)


def hunger_timer_loop():
    """Manage hunger system - Tamagotchi style!"""
    import sys
    sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
    from duck_hunger import HungerManager
    from duck_sms import SMSManager
    
    hunger_manager = HungerManager()
    sms_manager = SMSManager()
    
    # Reset at morning (6 AM)
    last_reset_day = None
    
    while True:
        time.sleep(60)  # Check every minute
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            
            # Morning reset at 6 AM
            if current_hour == 6 and current_time.day != last_reset_day:
                hunger_manager.reset_daily()
                last_reset_day = current_time.day
            
            # Increase hunger every hour (at XX:00)
            if current_time.minute == 0:
                hunger_manager.increase_hunger(amount=1.0)
            
            # Check if we should announce hunger (30 min after meal time)
            if hunger_manager.should_announce_hunger():
                announcement = "Jeg er sulten! Kan du gi meg mat? Send meg 🍪 cookie eller 🍕 pizza!"
                print(f"😋 {announcement}", flush=True)
                
                # Write announcement to file for voice
                with open('/tmp/duck_hunger_announcement.txt', 'w', encoding='utf-8') as f:
                    f.write(announcement)
                
                hunger_manager.mark_announcement_made()
            
            # Check if we should send SMS nag (10 min after announcement)
            if hunger_manager.should_send_sms_nag():
                # Get next contact to nag
                contacts = sms_manager.get_all_contacts()
                if contacts:
                    # Rotate through contacts
                    import random
                    contact = random.choice(contacts)
                    
                    message = f"Hei {contact['name']}! 🦆 Jeg er veldig sulten! Kan du sende meg 🍪 eller 🍕 på SMS? 😋"
                    result = sms_manager.send_sms(contact['phone'], message)
                    
                    if result['status'] == 'sent':
                        print(f"📤 Sent hunger SMS to {contact['name']}", flush=True)
                        hunger_manager.mark_sms_nag_sent()
                
        except Exception as e:
            print(f"⚠️ Hunger timer error: {e}", flush=True)


def heartbeat_loop():
    """Send heartbeat to relay every 5 minutes"""
    while True:
        time.sleep(300)  # 5 minutes
        try:
            register_with_relay()
        except Exception as e:
            print(f"⚠️ Heartbeat failed: {e}", flush=True)


def main():
    """Hovedloop for stemmeassistenten"""
    # Rydd opp gamle trigger-filer ved oppstart
    try:
        if os.path.exists('/tmp/duck_switch_network.txt'):
            os.remove('/tmp/duck_switch_network.txt')
            print("🧹 Ryddet opp gammel switch_network trigger", flush=True)
    except:
        pass
    
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
    
    # Initialiser SMS manager (for boredom status)
    try:
        from src.duck_sms import SMSManager
        sms_manager = SMSManager()
        print(f"✅ SMS Manager initialisert (boredom level: {sms_manager.get_boredom_level():.1f}/10)", flush=True)
    except Exception as e:
        print(f"⚠️ SMS Manager feilet (fortsetter uten): {e}", flush=True)
        sms_manager = None
    
    # Initialiser Hunger manager (for Tamagotchi hunger status)
    try:
        from src.duck_hunger import HungerManager
        hunger_manager = HungerManager()
        print(f"✅ Hunger Manager initialisert (hunger level: {hunger_manager.get_hunger_level():.1f}/10)", flush=True)
    except Exception as e:
        print(f"⚠️ Hunger Manager feilet (fortsetter uten): {e}", flush=True)
        hunger_manager = None
    
    # Register with SMS relay server
    register_with_relay()
    
    # Start heartbeat thread
    import threading  # Import here to avoid scope issues
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    print("✅ SMS relay heartbeat started", flush=True)
    
    # Start SMS polling thread
    sms_polling_thread = threading.Thread(target=sms_polling_loop, daemon=True)
    sms_polling_thread.start()
    print("✅ SMS polling started", flush=True)
    
    # Start boredom timer thread
    boredom_timer_thread = threading.Thread(target=boredom_timer_loop, daemon=True)
    boredom_timer_thread.start()
    print("✅ Boredom timer started (checks every hour)", flush=True)
    
    # Start hunger timer thread
    hunger_timer_thread = threading.Thread(target=hunger_timer_loop, daemon=True)
    hunger_timer_thread.start()
    print("✅ Hunger timer started (Tamagotchi mode activated! 🍪🍕)", flush=True)
    
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
    ai_thread = threading.Thread(target=check_ai_queries, args=(api_key, speech_config, beak, memory_manager, user_manager, sms_manager, hunger_manager), daemon=True)
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
    
    # Vent litt ekstra for å la nebbet fullføre bevegelsene
    time.sleep(0.5)
    
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
            elif external_message.startswith('__SMS_ANNOUNCEMENT__'):
                # SMS-annonsering mottatt
                announcement = external_message.replace('__SMS_ANNOUNCEMENT__', '', 1)
                speak(announcement, speech_config, beak)
                
                # Sjekk om det er en respons-annonsering
                sms_response_file = '/tmp/duck_sms_response.txt'
                time.sleep(1)
                if os.path.exists(sms_response_file):
                    try:
                        with open(sms_response_file, 'r', encoding='utf-8') as f:
                            response_announcement = f.read().strip()
                        if response_announcement:
                            time.sleep(0.5)
                            speak(response_announcement, speech_config, beak)
                        os.remove(sms_response_file)
                    except Exception as e:
                        print(f"⚠️ Error reading SMS response: {e}", flush=True)
                continue  # Gå tilbake til wake word etter SMS
            elif external_message.startswith('__HUNGER_ANNOUNCEMENT__'):
                # Hunger announcement
                announcement = external_message.replace('__HUNGER_ANNOUNCEMENT__', '', 1)
                speak(announcement, speech_config, beak)
                continue  # Gå tilbake til wake word
            elif external_message.startswith('__HOTSPOT_ANNOUNCEMENT__'):
                # Hotspot announcement
                announcement = external_message.replace('__HOTSPOT_ANNOUNCEMENT__', '', 1)
                speak(announcement, speech_config, beak)
                continue  # Gå tilbake til wake word
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
            # Normal wake word - si adaptiv hilsen
            # Hent nåværende bruker fra user_manager
            if user_manager:
                current_user = user_manager.get_current_user()
                user_name = current_user['display_name']
            else:
                user_name = 'på du'
            
            # Generer adaptiv hilsen basert på personlighetsprofil
            greeting_msg = get_adaptive_greeting(user_name=user_name)
            print(f"🎭 Adaptive greeting: {greeting_msg}", flush=True)
            
            speak(greeting_msg, speech_config, beak)
        
        # Reduce boredom when conversation starts
        try:
            import sys
            sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
            from duck_sms import SMSManager
            sms_manager = SMSManager()
            sms_manager.reduce_boredom(amount=2.0)
        except Exception as e:
            print(f"⚠️ Could not reduce boredom: {e}", flush=True)
        
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
            
            # Sjekk om bruker vil bytte nettverk (trigger fra AI funksjon)
            if os.path.exists('/tmp/duck_switch_network.txt'):
                try:
                    os.remove('/tmp/duck_switch_network.txt')
                    print("🔄 Bytter til hotspot-modus...", flush=True)
                    
                    # Koble ned alle WiFi-connections først
                    import subprocess
                    import time
                    get_active = subprocess.run(
                        ['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show', '--active'],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in get_active.stdout.strip().split('\n'):
                        if ':802-11-wireless' in line and not line.startswith('Hotspot:'):
                            conn_name = line.split(':')[0]
                            subprocess.run(['sudo', 'nmcli', 'connection', 'down', conn_name],
                                         capture_output=True, timeout=5)
                    
                    # Vent litt så WiFi er helt nede
                    time.sleep(2)
                    
                    # Kjør auto-hotspot.sh som håndterer alt (LED, announcement, portal, monitor)
                    subprocess.Popen(['/home/admog/Code/chatgpt-and/scripts/auto-hotspot.sh'])
                    
                    print("✅ Auto-hotspot startet!", flush=True)
                    
                except Exception as e:
                    print(f"⚠️ Kunne ikke bytte til hotspot: {e}", flush=True)
            
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
                result = chatgpt_query(
                    messages, 
                    api_key, 
                    memory_manager=memory_manager, 
                    user_manager=user_manager,
                    sms_manager=sms_manager,
                    hunger_manager=hunger_manager,
                    source="voice"
                )
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
                
                # Fjern AVSLUTT markør
                import re
                reply_clean = re.sub(r'\[?AVSLUTT\]?\.?', '', reply, flags=re.IGNORECASE).strip()
                reply_clean = ' '.join(reply_clean.split())
                
                # For TTS: fjern også emojis (de leses høyt som "smilende ansikt med smilende øyne")
                reply_for_speech = re.sub(r'[😀😁😂😃😄😅😆😇😈😉😊😋😌😍😎😏😐😑😒😓😔😕😖😗😘😙😚😛😜😝😞😟😠😡😢😣😤😥😦😧😨😩😪😫😬😭😮😯😰😱😲😳😴😵😶😷😸😹😺😻😼😽😾😿🙀🙁🙂🙃🙄🙅🙆🙇🙈🙉🙊🙋🙌🙍🙎🙏✨💡🎉🎭👍👎💬🔧📚🎯🚀✅❌⚠️🏠🌡️💻📱⏰🔔🎵🎶📧📅✉️🔥💪🤔🤗🤩🥳🤪🤨🤯🤬😺🎃👻💀☠️👽🤖💩🦆🐦🐤]', '', reply_clean).strip()
                
                print("ChatGPT svar:", reply_clean, flush=True)  # Logg med emojis
                if ai_wants_to_end:
                    print("🔚 AI detekterte samtale-avslutning", flush=True)
                
                speak(reply_for_speech, speech_config, beak)  # TTS uten emojis
                messages.append({"role": "assistant", "content": reply_clean})  # Historikk med emojis
                
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
