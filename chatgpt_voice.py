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
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# Duck moduler
from scripts.hardware.duck_beak import Beak, CLOSE_DEG, OPEN_DEG, TRIM_DEG, SERVO_CHANNEL
from scripts.hardware.rgb_duck import set_blue, off, blink_yellow_purple, pulse_blue, stop_blink, set_yellow
from src.duck_config import MESSAGES_FILE
from src.duck_memory import MemoryManager
from src.duck_user_manager import UserManager
from src.duck_audio import speak
from src.duck_speech import wait_for_wake_word, recognize_speech_from_mic
from src.duck_music import play_song
from src.duck_conversation import check_ai_queries, ask_for_user_switch, is_conversation_ending
from src.duck_ai import chatgpt_query, generate_message_metadata
from src.adaptive_greetings import get_adaptive_greeting, get_adaptive_goodbye
from src.duck_sleep import is_sleeping, get_sleep_status

# ServiceManager for delt state mellom tjenester
from src.duck_services import get_services

# Flush stdout umiddelbart slik at print vises i journalctl
sys.stdout.reconfigure(line_buffering=True)

# MAX98357A SD pin skal kobles til fast 3.3V (pin 1 eller 17)
print("MAX98357A SD pin skal være koblet til 3.3V - forsterker alltid på", flush=True)


def is_hotspot_active():
    """Sjekk om WiFi hotspot er aktivt via NetworkManager"""
    try:
        result = subprocess.run(
            ['nmcli', 'connection', 'show', '--active'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return 'Hotspot' in result.stdout
    except Exception:
        return False


def cleanup():
    """Cleanup-funksjon som slår av alle LED ved avslutning"""
    print("Slår av LED og rydder opp...", flush=True)
    from scripts.hardware.rgb_duck import stop_blink, off
    stop_blink()
    off()


# Registrer cleanup ved normal exit og ved signaler
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), sys.exit(0)))


def register_with_relay():
    """Register Duck with SMS relay server on startup"""
    base_url = os.getenv('SMS_RELAY_URL', 'https://sms-relay.duckberry.no')
    # Ensure we add /register endpoint
    relay_url = base_url.rstrip('/') + '/register'
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


def _send_duck_response(from_duck, message_text, media_url, messenger, sms_manager):
    """Generate and send response to duck message (called after delay)"""
    from duck_services import get_services
    from duck_ai import chatgpt_query
    
    services = get_services()
    memory_manager = services.get_memory_manager()
    
    # Build context and generate response
    relation = messenger.get_duck_relation(from_duck)
    prompt = f"""Du fikk nettopp en melding fra {relation}:
"{message_text}"

Skriv et kort, hyggelig svar. Dere er and-venner som bor hos forskjellige folk.
Hold det kort og personlig (maks 160 tegn)."""
    
    messages_context = [{"role": "user", "content": prompt}]
    response_tuple = chatgpt_query(
        messages_context,
        api_key=os.getenv('OPENAI_API_KEY'),
        model="gpt-4o",
        enable_tools=False  # Disable tools for auto-response to avoid recursion
    )
    
    if response_tuple:
        response = response_tuple[0] if isinstance(response_tuple, tuple) else response_tuple
        # Log and send response
        messenger.log_message(
            from_duck=os.getenv('DUCK_NAME', 'Samantha').lower(),
            to_duck=from_duck,
            message=response,
            direction='sent',
            initiated=False,
            tokens_used=len(response.split())
        )
        
        sms_manager.send_duck_message(from_duck, response)
        print(f"🦆📤 Sent response to {from_duck}: {response[:50]}...", flush=True)
        
        # Write response announcement to file for main loop to speak
        with open('/tmp/duck_response_announcement.txt', 'w', encoding='utf-8') as f:
            f.write(json.dumps({
                'response': response,
                'to_duck': from_duck
            }))
        
        # Save to memory
        memory_manager.save_message(
            user_text=message_text,
            ai_response=response,
            user_name=from_duck
        )


def sms_polling_loop():
    """Poll relay for new SMS messages and duck-to-duck messages every 10 seconds"""
    import sys
    sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
    from duck_sms import SMSManager
    from duck_messenger import DuckMessenger
    from duck_services import get_services
    
    relay_url = os.getenv('SMS_RELAY_URL', 'https://sms-relay.duckberry.no/register')
    base_url = relay_url.replace('/register', '')
    twilio_number = os.getenv('TWILIO_NUMBER')
    duck_name = os.getenv('DUCK_NAME', 'Samantha')
    
    if not twilio_number:
        print("⚠️ TWILIO_NUMBER not set - skipping SMS polling", flush=True)
        return
    
    # Initialize managers
    sms_manager = SMSManager()
    messenger = DuckMessenger()
    
    # Køy for ventende duck message svar (lagrer når vi skal svare)
    pending_duck_responses = []  # [(respond_at_time, from_duck, message_text, media_url), ...]
    
    # URL encode the number for SMS polling
    import urllib.parse
    encoded_number = urllib.parse.quote(twilio_number, safe='')
    poll_url = f"{base_url}/poll/{encoded_number}"
    
    while True:
        time.sleep(10)  # Poll every 10 seconds
        
        # Sjekk om det er tid til å svare på ventende duck messages
        current_time = datetime.now()
        responses_to_send = [item for item in pending_duck_responses if item[0] <= current_time]
        pending_duck_responses = [item for item in pending_duck_responses if item[0] > current_time]
        
        for respond_at, from_duck, message_text, media_url in responses_to_send:
            try:
                print(f"⏰ Tid til å svare til {from_duck}!", flush=True)
                # Generate and send response
                _send_duck_response(from_duck, message_text, media_url, messenger, sms_manager)
            except Exception as e:
                print(f"⚠️ Error sending delayed duck response: {e}", flush=True)
        
        # 1. Poll for SMS messages
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
                            media_url = msg.get('media_url')  # MMS image URL
                            
                            print(f"📱 SMS from {from_number}: {message_text[:50]}...", flush=True)
                            
                            # Check if it's an MMS with image
                            if media_url:
                                print(f"📸 MMS contains image: {media_url}", flush=True)
                                
                                # Process MMS image
                                from src.duck_vision import VisionAnalyzer, VisionConfig
                                from src.duck_memory import MemoryManager
                                
                                # Check if vision is enabled
                                if VisionConfig.ENABLED:
                                    try:
                                        # Get contact info
                                        from src.duck_services import get_services
                                        services = get_services()
                                        sms_manager = services.get_sms_manager()
                                        contact_result = sms_manager.get_contact_by_phone(from_number)
                                        
                                        sender_name = from_number
                                        sender_relation = ""
                                        if contact_result.get('status') == 'ok':
                                            contact = contact_result.get('contact')
                                            sender_name = contact.get('name', from_number)
                                            sender_relation = contact.get('relation', '')
                                        
                                        # Analyze image
                                        api_key = os.getenv('OPENAI_API_KEY')
                                        vision = VisionAnalyzer(api_key)
                                        memory_manager = services.get_memory_manager()
                                        
                                        analysis = vision.process_mms(
                                            image_url=media_url,
                                            sender_name=sender_name,
                                            message_text=message_text,
                                            memory_manager=memory_manager,
                                            sender_relation=sender_relation
                                        )
                                        
                                        if analysis:
                                            # Announce the image
                                            description = analysis['description']
                                            announcement = f"Jeg fikk et bilde fra {sender_name}! {description}"
                                            
                                            if message_text:
                                                announcement += f" De skrev: {message_text}"
                                            
                                            print(f"🖼️  Image description: {description}", flush=True)
                                            
                                            # Write announcement to file
                                            with open('/tmp/duck_sms_announcement.txt', 'w', encoding='utf-8') as f:
                                                f.write(announcement)
                                            
                                            # Check if there are people in the image
                                            people_count = 0
                                            desc_lower = description.lower()
                                            if 'person' in desc_lower or 'menneske' in desc_lower or 'mann' in desc_lower or 'kvinne' in desc_lower:
                                                # Extract number of people if mentioned
                                                import re
                                                numbers = re.findall(r'\b(\d+|en|to|tre|fire|fem|seks|sju|åtte|ni|ti)\b', desc_lower)
                                                if numbers:
                                                    number_map = {'en': 1, 'to': 2, 'tre': 3, 'fire': 4, 'fem': 5, 
                                                                'seks': 6, 'sju': 7, 'åtte': 8, 'ni': 9, 'ti': 10}
                                                    people_count = number_map.get(numbers[0], 0)
                                                    if people_count == 0 and numbers[0].isdigit():
                                                        people_count = int(numbers[0])
                                            
                                            # If people detected, prepare follow-up question
                                            if people_count > 0:
                                                followup = f" Hvem er de {people_count} personene på bildet?"
                                                # Store for later use in conversation
                                                with open('/tmp/duck_image_followup.txt', 'w', encoding='utf-8') as f:
                                                    f.write(f"{analysis['image_id']}|{followup}")
                                        
                                    except Exception as e:
                                        print(f"⚠️ MMS processing failed: {e}", flush=True)
                                        import traceback
                                        traceback.print_exc()
                                else:
                                    print("⚠️ Vision features disabled - skipping image analysis", flush=True)
                            
                            # Forward to SMS handler (for text processing)
                            import sys
                            sys.path.insert(0, '/home/admog/Code/chatgpt-and/src')
                            from src.duck_services import get_services
                            from duck_audio import speak
                            
                            services = get_services()
                            sms_manager = services.get_sms_manager()
                            result = sms_manager.handle_incoming_sms(from_number, message_text)
                            
                            # Announce SMS with voice (only if not already announced as MMS)
                            if not media_url and result.get('status') == 'ok':
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
                                        contact, message_text, fed=result.get('fed', False)
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
        
        # Also poll for duck-to-duck messages
        try:
            messages = sms_manager.poll_duck_messages()
            
            if messages:
                print(f"🦆📬 Received {len(messages)} duck message(s)", flush=True)
                for msg in messages:
                    from_duck = msg['from_duck']
                    message_text = msg['message']
                    media_url = msg.get('media_url')
                    
                    print(f"   From {from_duck}: {message_text[:50]}...", flush=True)
                    
                    # ALLTID logg mottatte meldinger først (uansett loop)
                    messenger.log_message(
                        from_duck=from_duck,
                        to_duck=os.getenv('DUCK_NAME', 'Samantha').lower(),
                        message=message_text,
                        direction='received',
                        initiated=False,
                        tokens_used=len(message_text.split())
                    )
                    print(f"✅ Logged incoming message from {from_duck}", flush=True)
                    
                    # Check for loop BEFORE scheduling response
                    if messenger.detect_loop(from_duck, message_text):
                        print(f"⚠️ Loop detektert med {from_duck}, hopper over SVAR (melding er logget)", flush=True)
                        continue
                    
                    # Random delay før svar (30 sek til 4 min) - legg til i køy
                    import random
                    delay_seconds = random.randint(30, 240)  # 30 sek til 4 min
                    respond_at = datetime.now() + timedelta(seconds=delay_seconds)
                    pending_duck_responses.append((respond_at, from_duck, message_text, media_url))
                    print(f"⏱️ Planlagt svar til {from_duck} om {delay_seconds} sekunder (kl {respond_at.strftime('%H:%M:%S')})", flush=True)
                    
                    # Format announcement for immediate playback
                    announcement = messenger.format_incoming_announcement(from_duck, message_text)
                    
                    print(f"🦆💬 Message from {from_duck}: {message_text[:50]}...", flush=True)
                    
                    # Write announcement to file for main loop to speak
                    with open('/tmp/duck_message_announcement.txt', 'w', encoding='utf-8') as f:
                        f.write(json.dumps({
                            'announcement': announcement,
                            'from_duck': from_duck,
                            'message': message_text,
                            'media_url': media_url
                        }))
        except Exception as e:
            print(f"⚠️ Duck message polling error: {e}", flush=True)


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
            print(f"🕐 Boredom level: {new_level:.1f}/10", flush=True)
            
            # MIDDELS KJEDSOMHET (5-6.5): Synge en sang
            if 5.0 <= new_level < 7.0:
                import random
                import os
                from src.duck_music import play_song
                
                # 50% sjanse for å synge når hun kjeder seg litt
                if random.random() < 0.5:
                    musikk_dir = "/home/admog/Code/chatgpt-and/musikk"
                    available_songs = [d for d in os.listdir(musikk_dir) 
                                     if os.path.isdir(os.path.join(musikk_dir, d)) and 
                                     os.path.exists(os.path.join(musikk_dir, d, "duck_mix.wav"))]
                    
                    if available_songs:
                        random_song = random.choice(available_songs)
                        song_folder = os.path.join(musikk_dir, random_song)
                        
                        print(f"🎵 Anda kjeder seg (level {new_level:.1f}) - synger {random_song}", flush=True)
                        
                        # Skriv annonsering til fil
                        announcement = f"Jeg kjeder meg litt, så jeg skal synge {random_song}!"
                        with open('/tmp/duck_song_announcement.txt', 'w', encoding='utf-8') as f:
                            f.write(announcement)
                        
                        # Spill sangen
                        play_song(song_folder, beak, speech_config)
                        
                        # Reduser kjedsomhet etter sang
                        sms_manager.reduce_boredom(amount=2.0)
                        print(f"✅ Sang ferdig - boredom redusert til {sms_manager.get_boredom_level():.1f}/10", flush=True)
            
            # HØY KJEDSOMHET (≥7): Send SMS
            if sms_manager.check_boredom_trigger():
                # TIDSBEGRENSNING: Ikke send boredom SMS mellom 01:00 og 07:00
                from datetime import datetime
                current_hour = datetime.now().hour
                if 1 <= current_hour < 7:
                    print(f"😴 Boredom SMS blokkert: Nattetid ({current_hour:02d}:00)", flush=True)
                    # Reduser litt så vi ikke bygger opp masse boredom om natten
                    sms_manager.reduce_boredom(amount=1.0)
                else:
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
    from duck_services import get_services
    
    services = get_services()
    hunger_manager = services.get_hunger_manager()
    sms_manager = services.get_sms_manager()
    
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
                # TIDSBEGRENSNING: Ikke send hunger SMS mellom 01:00 og 07:00
                current_hour = current_time.hour
                if 1 <= current_hour < 7:
                    print(f"😴 Hunger SMS blokkert: Nattetid ({current_hour:02d}:00)", flush=True)
                    # Mark as sent så vi ikke prøver igjen umiddelbart
                    hunger_manager.mark_sms_nag_sent()
                else:
                    # Get next contact using smart weighted random
                    contact = sms_manager.get_next_contact_weighted()
                    if contact:
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


# ═══════════════════════════════════════════════════════════════════════
# FACE RECOGNITION HANDLERS
# ═══════════════════════════════════════════════════════════════════════

# Global state for face learning workflow
_waiting_for_name = False
_pending_person_name = None
_waiting_for_confirmation = False


def on_face_recognized(name: str, confidence: float):
    """Callback når kjent ansikt gjenkjennes (LEGACY - ikke brukt uten continuous streaming)"""
    pass


def on_unknown_face():
    """Callback når ukjent ansikt detekteres (LEGACY - ikke brukt uten continuous streaming)"""
    pass


def on_learning_progress(name: str, step: int, total: int, instruction: str):
    """Callback under face learning - gi stemme-instruksjoner"""
    try:
        services = get_services()
        # Get speech config from main scope (will be set in main())
        if hasattr(on_learning_progress, 'speech_config') and hasattr(on_learning_progress, 'beak'):
            speak(instruction, on_learning_progress.speech_config, on_learning_progress.beak)
            print(f"📸 {step}/{total}: {instruction}", flush=True)
        else:
            print(f"📸 {step}/{total}: {instruction}", flush=True)
    except Exception as e:
        print(f"⚠️ Error in learning_progress callback: {e}", flush=True)


def check_if_waiting_for_name():
    """Check if we're waiting for user to give their name"""
    print(f"🔍 check_if_waiting_for_name() returning: {_waiting_for_name}", flush=True)
    return _waiting_for_name


def handle_name_response(user_text: str, speech_config, beak) -> bool:
    """
    Handle user response when waiting for name.
    Returns True if handled, False otherwise.
    """
    global _waiting_for_name, _pending_person_name, _waiting_for_confirmation
    
    print(f"🔍 handle_name_response called: _waiting_for_name={_waiting_for_name}, _waiting_for_confirmation={_waiting_for_confirmation}", flush=True)
    
    if _waiting_for_name:
        # Extract name from response
        import re
        
        # Strip punctuation
        user_text_clean = user_text.strip().rstrip('.,!?')
        
        # Use Unicode word characters to match Norwegian letters (æøå)
        # Match multiple words to catch full names
        patterns = [
            r"jeg heter ([a-zæøåA-ZÆØÅ\s]+)",
            r"mitt navn er ([a-zæøåA-ZÆØÅ\s]+)",
            r"navnet mitt er ([a-zæøåA-ZÆØÅ\s]+)",
            r"jeg er ([a-zæøåA-ZÆØÅ\s]+)",
            r"det er ([a-zæøåA-ZÆØÅ\s]+)",
            r"^([a-zæøåA-ZÆØÅ\s]+)$"  # Just the name(s)
        ]
        
        name = None
        for pattern in patterns:
            match = re.search(pattern, user_text_clean.lower())
            if match:
                # Clean up: remove extra spaces, capitalize each word
                name_raw = match.group(1).strip()
                # Remove words like "jo", "bare", etc that aren't names
                filler_words = ['jo', 'bare', 'vel', 'altså', 'liksom', 'da', 'men']
                name_words = [w.capitalize() for w in name_raw.split() if w not in filler_words]
                if name_words:
                    name = ' '.join(name_words)
                    break
        
        if name:
            print(f"✅ Name extracted: '{name}'", flush=True)
            speak(f"Hyggelig å møte deg, {name}! Kan jeg lagre deg?", speech_config, beak)
            _pending_person_name = name
            _waiting_for_name = False
            _waiting_for_confirmation = True
            return True
        else:
            print(f"❌ Name extraction failed for: '{user_text}'", flush=True)
            speak("Beklager, jeg hørte ikke navnet ditt. Hvem er du?", speech_config, beak)
            return True
    
    elif _waiting_for_confirmation:
        # User confirms/denies learning
        if "ja" in user_text.lower() or "ok" in user_text.lower():
            try:
                services = get_services()
                vision_service = services.get_vision_service()
                
                speak("Perfekt! Vi tar 5 bilder. Beveg hodet litt når jeg ber deg om det.", speech_config, beak)
                
                # Save name before calling learn_person (in case callback resets it)
                name_to_learn = _pending_person_name
                vision_service.learn_person(name_to_learn, num_samples=5)
                
                # Wait for learning to complete
                # Each image takes ~2 seconds (1.5s TTS instruction + 0.8s capture + processing)
                time.sleep(15)  # 5 images * 2.5s + extra buffer
                speak(f"Ferdig! Nå husker jeg deg, {name_to_learn}!", speech_config, beak)
                
            except Exception as e:
                print(f"⚠️ Error learning person: {e}", flush=True)
                speak("Beklager, noe gikk galt.", speech_config, beak)
            
            _pending_person_name = None
            _waiting_for_confirmation = False
            return True
        else:
            speak("Ok, jeg lagrer deg ikke.", speech_config, beak)
            _pending_person_name = None
            _waiting_for_confirmation = False
            return True
    
    return False


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
    
    # Initialiser ServiceManager (delt state med kontrollpanel)
    try:
        services = get_services()
        memory_manager = services.get_memory_manager()
        user_manager = services.get_user_manager()
        sms_manager = services.get_sms_manager()
        hunger_manager = services.get_hunger_manager()
        vision_service = services.get_vision_service()
        
        current_user = user_manager.get_current_user()
        print(f"✅ ServiceManager initialisert - bruker: {current_user['display_name']}", flush=True)
        print(f"   Boredom: {sms_manager.get_boredom_level():.1f}/10, Hunger: {hunger_manager.get_hunger_level():.1f}/10", flush=True)
        
        # Start Duck-Vision service (optional, fails gracefully if not available)
        # NOTE: Will be started after speech_config is initialized
        print("🦆 Duck-Vision will be started after speech_config init...", flush=True)
            
    except Exception as e:
        print(f"⚠️ ServiceManager feilet: {e}", flush=True)
        memory_manager = None
        user_manager = None
        sms_manager = None
        hunger_manager = None
        vision_service = None
    
    # Register with SMS relay server
    register_with_relay()
    
    # Start heartbeat thread
    import threading  # Import here to avoid scope issues
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    print("✅ SMS relay heartbeat started", flush=True)
    
    # Start SMS polling thread (now also handles duck-to-duck messages)
    sms_polling_thread = threading.Thread(target=sms_polling_loop, daemon=True)
    sms_polling_thread.start()
    print("✅ SMS and duck-to-duck message polling started", flush=True)
    
    # Start boredom timer thread
    boredom_timer_thread = threading.Thread(target=boredom_timer_loop, daemon=True)
    boredom_timer_thread.start()
    print("✅ Boredom timer started (checks every hour)", flush=True)
    
    # Start hunger timer thread
    hunger_timer_thread = threading.Thread(target=hunger_timer_loop, daemon=True)
    hunger_timer_thread.start()
    print("✅ Hunger timer started (Tamagotchi mode activated! 🍪🍕)", flush=True)
    
    # Start 3D printer monitoring thread
    try:
        from src.duck_prusa import get_prusa_manager
        
        def on_print_finished(job_name):
            """Callback når 3D-print er ferdig"""
            try:
                message = f"🖨️ 3D-printen din er ferdig! {job_name} er klar til å plukkes opp."
                # speech_config er ikke tilgjengelig ennå, så vi lagrer meldingen til senere
                trigger_file = '/tmp/duck_prusa_announcement.txt'
                with open(trigger_file, 'w', encoding='utf-8') as f:
                    f.write(message)
                print(f"✅ Prusa: Print ferdig - {job_name}", flush=True)
            except Exception as e:
                print(f"⚠️ Prusa callback feilet: {e}", flush=True)
        
        prusa = get_prusa_manager()
        if prusa.is_configured():
            prusa.start_monitoring(
                on_print_finished=on_print_finished,
                on_print_failed=lambda job: print(f"⚠️ Prusa: Print feilet - {job}", flush=True)
            )
            print("✅ 3D printer monitoring started", flush=True)
        else:
            print("ℹ️ 3D printer not configured (PRUSA_API_TOKEN/PRUSA_PRINTER_UUID missing)", flush=True)
    except Exception as e:
        print(f"⚠️ 3D printer monitoring kunne ikke startes: {e}", flush=True)
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"
    
    # Start Duck-Vision service NOW (after speech_config is available)
    if vision_service:
        try:
            print("🦆 Starting Duck-Vision service...", flush=True)
            
            # Set up speech_config and beak for learning progress callback
            on_learning_progress.speech_config = speech_config
            on_learning_progress.beak = beak
            
            vision_connected = vision_service.start(
                on_face_detected=on_face_recognized,
                on_unknown_face=on_unknown_face,
                on_learning_progress=on_learning_progress
            )
            if vision_connected:
                # Wait briefly for MQTT on_connect callback to set connected flag
                time.sleep(0.5)
                print("✅ Duck-Vision connected!", flush=True)
            else:
                print("⚠️ Duck-Vision not available (is Duck-Vision running on Pi 5?)", flush=True)
        except Exception as e:
            print(f"⚠️ Duck-Vision initialization error: {e}", flush=True)

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
    ai_thread = threading.Thread(target=check_ai_queries, args=(api_key, speech_config, beak, memory_manager, user_manager, sms_manager, hunger_manager, vision_service), daemon=True)
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
    
    # Sjekk FØRST om det finnes en hotspot-annonsering (prioriteres over normal greeting)
    hotspot_announcement_file = '/tmp/duck_hotspot_announcement.txt'
    hotspot_audio_file = '/home/admog/Code/chatgpt-and/audio/hotspot_announcement.wav'
    hotspot_active = False
    greeting_success = False
    
    if os.path.exists(hotspot_announcement_file):
        try:
            # Les announcement-filen (for logging)
            with open(hotspot_announcement_file, 'r', encoding='utf-8') as f:
                announcement = f.read().strip()
            os.remove(hotspot_announcement_file)
            
            if announcement:
                print(f"📡 Hotspot-modus: Spiller forhåndsinnspilt melding", flush=True)
                # Sett LED til gul for hotspot-modus
                set_yellow()
                hotspot_active = True
                time.sleep(0.5)
                
                # Spill forhåndsinnspilt audio-fil (fungerer uten internett)
                if os.path.exists(hotspot_audio_file):
                    try:
                        # Bruk aplay til å spille WAV-filen
                        import subprocess
                        subprocess.run(['aplay', '-q', hotspot_audio_file], check=True)
                        print("✅ Hotspot announcement spilt - LED forblir gul", flush=True)
                        greeting_success = True
                        
                        # Åpne og lukk nebbet synkront med audio
                        if beak:
                            time.sleep(0.5)
                            beak.close()
                    except Exception as e:
                        print(f"⚠️ Kunne ikke spille hotspot audio: {e}", flush=True)
                else:
                    print(f"⚠️ Hotspot audio-fil ikke funnet: {hotspot_audio_file}", flush=True)
                    print(f"   Kjør: .venv/bin/python scripts/generate_hotspot_audio.py", flush=True)
        except Exception as e:
            print(f"⚠️ Error reading hotspot announcement at startup: {e}", flush=True)
    
    # Hvis ikke hotspot-modus, si normal greeting
    if not hotspot_active:
        if ip_address and ip_address != "127.0.0.1":
            greeting = messages_config['startup_messages']['with_network'].replace('{ip}', ip_address.replace('.', ' punkt '))
            print(f"Oppstartshilsen med IP: {ip_address}", flush=True)
        else:
            greeting = messages_config['startup_messages']['without_network']
            print("Oppstartshilsen uten IP (nettverk ikke klart)", flush=True)
        
        # Prøv å si oppstartshilsen flere ganger hvis TTS/nettverk ikke er klart
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
        print("Oppstartshilsen/hotspot-melding kunne ikke sies etter 3 forsøk - fortsetter uten hilsen", flush=True)
    
    # Sett LED basert på hotspot status (kun hvis ikke allerede satt)
    if not hotspot_active:
        if is_hotspot_active():
            set_yellow()
            print("📡 Hotspot er aktivt - LED er gul", flush=True)
        else:
            set_blue()
    # Hvis hotspot_active=True er LED allerede gul fra hotspot-meldingen
    
    # Vent litt ekstra for å la nebbet fullføre bevegelsene
    time.sleep(0.5)
    
    print("Anda venter på wake word... (si 'quack quack')", flush=True)
    
    # Session tracking: Generer ny session_id ved hver samtale
    current_session_id = None
    session_start_time = None
    SESSION_TIMEOUT_MINUTES = 30
    
    # Sleep mode tracking
    sleep_led_active = False
    
    while True:
        # Sjekk sleep mode først
        if is_sleeping():
            # Start blå pulsering bare én gang
            if not sleep_led_active:
                pulse_blue()
                sleep_led_active = True
                print("💤 Sleep mode aktiv - ignorerer wake words (blå pulsering)", flush=True)
            
            # Sjekk SMS/hunger/hotspot SELV I SØVNMODUS (skal alltid leses opp!)
            # Sjekk SMS-annonseringer
            sms_announcement_file = '/tmp/duck_sms_announcement.txt'
            if os.path.exists(sms_announcement_file):
                try:
                    with open(sms_announcement_file, 'r', encoding='utf-8') as f:
                        announcement = f.read().strip()
                    os.remove(sms_announcement_file)
                    if announcement:
                        print(f"📬 [SLEEP MODE] SMS announcement: {announcement[:50]}...", flush=True)
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
                        # Sett RGB tilbake til sleep mode etter SMS
                        pulse_blue()
                except Exception as e:
                    print(f"⚠️ Error reading SMS announcement: {e}", flush=True)
            
            # Sjekk duck-to-duck message announcements
            duck_msg_file = '/tmp/duck_message_announcement.txt'
            if os.path.exists(duck_msg_file):
                try:
                    with open(duck_msg_file, 'r', encoding='utf-8') as f:
                        data = json.loads(f.read())
                    os.remove(duck_msg_file)
                    
                    announcement = data.get('announcement')
                    if announcement:
                        print(f"🦆💬 [SLEEP MODE] Duck message: {announcement[:50]}...", flush=True)
                        speak(announcement, speech_config, beak)
                        pulse_blue()  # Sett RGB tilbake til sleep mode
                except Exception as e:
                    print(f"⚠️ Error reading duck message: {e}", flush=True)
            
            # Sjekk duck-to-duck response announcements
            duck_response_file = '/tmp/duck_response_announcement.txt'
            if os.path.exists(duck_response_file):
                try:
                    with open(duck_response_file, 'r', encoding='utf-8') as f:
                        data = json.loads(f.read())
                    os.remove(duck_response_file)
                    
                    response = data.get('response')
                    if response:
                        print(f"🦆📤 [SLEEP MODE] Duck response: {response[:50]}...", flush=True)
                        speak(response, speech_config, beak)
                        pulse_blue()  # Sett RGB tilbake til sleep mode
                except Exception as e:
                    print(f"⚠️ Error reading duck response: {e}", flush=True)
            
            # Sjekk sang-annonseringer (når Anda synger av kjedsomhet)
            song_announcement_file = '/tmp/duck_song_announcement.txt'
            if os.path.exists(song_announcement_file):
                try:
                    with open(song_announcement_file, 'r', encoding='utf-8') as f:
                        announcement = f.read().strip()
                    os.remove(song_announcement_file)
                    if announcement:
                        print(f"🎵 [SLEEP MODE] Song announcement: {announcement[:50]}...", flush=True)
                        speak(announcement, speech_config, beak)
                        # Sett RGB tilbake til sleep mode etter speaking
                        pulse_blue()
                except Exception as e:
                    print(f"⚠️ Error reading song announcement: {e}", flush=True)
            
            # Sjekk hunger-annonseringer
            hunger_announcement_file = '/tmp/duck_hunger_announcement.txt'
            if os.path.exists(hunger_announcement_file):
                try:
                    with open(hunger_announcement_file, 'r', encoding='utf-8') as f:
                        announcement = f.read().strip()
                    os.remove(hunger_announcement_file)
                    if announcement:
                        print(f"😋 [SLEEP MODE] Hunger announcement: {announcement[:50]}...", flush=True)
                        speak(announcement, speech_config, beak)
                        # Sett RGB tilbake til sleep mode etter speaking
                        pulse_blue()
                except Exception as e:
                    print(f"⚠️ Error reading hunger announcement: {e}", flush=True)
            
            # Sjekk hotspot-annonseringer
            hotspot_announcement_file = '/tmp/duck_hotspot_announcement.txt'
            if os.path.exists(hotspot_announcement_file):
                try:
                    with open(hotspot_announcement_file, 'r', encoding='utf-8') as f:
                        announcement = f.read().strip()
                    os.remove(hotspot_announcement_file)
                    if announcement:
                        print(f"📡 [SLEEP MODE] Hotspot announcement: {announcement[:50]}...", flush=True)
                        speak(announcement, speech_config, beak)
                        # Sett RGB tilbake til sleep mode etter speaking
                        pulse_blue()
                except Exception as e:
                    print(f"⚠️ Error reading hotspot announcement: {e}", flush=True)
            
            # Sjekk Prusa-annonseringer
            prusa_announcement_file = '/tmp/duck_prusa_announcement.txt'
            if os.path.exists(prusa_announcement_file):
                try:
                    with open(prusa_announcement_file, 'r', encoding='utf-8') as f:
                        announcement = f.read().strip()
                    os.remove(prusa_announcement_file)
                    if announcement:
                        print(f"🖨️ [SLEEP MODE] Prusa announcement: {announcement[:50]}...", flush=True)
                        speak(announcement, speech_config, beak)
                        # Sett RGB tilbake til sleep mode etter speaking
                        pulse_blue()
                except Exception as e:
                    print(f"⚠️ Error reading prusa announcement: {e}", flush=True)
            
            # Vent 0.5 sekunder før vi sjekker igjen (for rask respons)
            time.sleep(0.5)
            continue
        else:
            # Reset flag når ikke i sleep mode
            if sleep_led_active:
                stop_blink()
                set_blue()  # Tilbake til blå LED (klar for wake word)
                sleep_led_active = False
                print("⏰ Sleep mode deaktivert - våkner opp", flush=True)
        
        # Sjekk sang-forespørsler UTENFOR sleep mode (alltid!)
        song_request_file = '/tmp/duck_song_request.txt'
        if os.path.exists(song_request_file):
            try:
                with open(song_request_file, 'r', encoding='utf-8') as f:
                    song_folder = f.read().strip()
                os.remove(song_request_file)
                if song_folder and os.path.exists(song_folder):
                    print(f"🎵 Playing song from request: {song_folder}", flush=True)
                    from src.duck_music import play_song
                    play_song(song_folder, beak, speech_config)
                    # Etter sangen, fortsett normal loop
            except Exception as e:
                print(f"⚠️ Error playing song: {e}", flush=True)
        
        # Sjekk Prusa-annonseringer UTENFOR sleep mode
        prusa_announcement_file = '/tmp/duck_prusa_announcement.txt'
        if os.path.exists(prusa_announcement_file):
            try:
                with open(prusa_announcement_file, 'r', encoding='utf-8') as f:
                    announcement = f.read().strip()
                os.remove(prusa_announcement_file)
                if announcement:
                    print(f"🖨️ Prusa announcement: {announcement[:50]}...", flush=True)
                    speak(announcement, speech_config, beak)
            except Exception as e:
                print(f"⚠️ Error reading prusa announcement: {e}", flush=True)
        
        # SMS og duck messages sjekkes nå inne i wait_for_wake_word()
        # (Ingen dobbeltsjekking nødvendig her)
        
        # Normal wake word detection
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
            elif external_message.startswith('__DUCK_MESSAGE__'):
                # Duck-to-duck message announcement
                announcement = external_message.replace('__DUCK_MESSAGE__', '', 1)
                speak(announcement, speech_config, beak)
                
                # Sjekk om det er en respons-annonsering
                duck_response_file = '/tmp/duck_response_announcement.txt'
                time.sleep(1)
                if os.path.exists(duck_response_file):
                    try:
                        with open(duck_response_file, 'r', encoding='utf-8') as f:
                            data = json.loads(f.read())
                        response = data.get('response')
                        if response:
                            time.sleep(0.5)
                            speak(response, speech_config, beak)
                        os.remove(duck_response_file)
                    except Exception as e:
                        print(f"⚠️ Error reading duck response: {e}", flush=True)
                continue  # Gå tilbake til wake word etter duck message
            elif external_message.startswith('__HUNGER_ANNOUNCEMENT__'):
                # Hunger announcement
                announcement = external_message.replace('__HUNGER_ANNOUNCEMENT__', '', 1)
                speak(announcement, speech_config, beak)
                continue  # Gå tilbake til wake word
            elif external_message.startswith('__HUNGER_FED__'):
                # Fed from control panel
                announcement = external_message.replace('__HUNGER_FED__', '', 1)
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
            
            # Name mapping for face recognition (Åsmund = Osmund)
            face_name_mapping = {
                'åsmund': 'Osmund',
                'Åsmund': 'Osmund'
            }
            
            # Sjekk hvem som er der med Duck-Vision (prøver 3 ganger)
            vision_recognized = False
            if vision_service and vision_service.is_connected():
                try:
                    found, name, confidence = vision_service.check_person(timeout=5.0)
                    
                    if found and name:
                        # Map face recognition name to memory system name
                        mapped_name = face_name_mapping.get(name, name)
                        print(f"👋 Gjenkjent {name} ({confidence:.2%}) -> mapped to {mapped_name}", flush=True)
                        user_name = mapped_name
                        vision_recognized = True
                    else:
                        # Unknown or no person - use generic greeting
                        # Learning will be initiated by user during conversation if desired
                        print(f"👤 Ukjent eller ingen person - bruker fallback: {user_name}", flush=True)
                    
                except Exception as e:
                    print(f"⚠️ Error checking person: {e}", flush=True)
            else:
                print("⚠️ Duck-Vision not available or not connected", flush=True)
            
            # Generer adaptiv hilsen basert på personlighetsprofil
            if vision_recognized:
                # Enklere hilsen når face recognition gjenkjenner
                greeting_msg = f"Hei, {user_name}! Hyggelig å se deg igjen!"
                print(f"🎭 Face recognition greeting: {greeting_msg}", flush=True)
            else:
                # Full adaptiv hilsen når ikke gjenkjent visuelt
                greeting_msg = get_adaptive_greeting(user_name=user_name)
                print(f"🎭 Adaptive greeting (via user_manager fallback): {greeting_msg}", flush=True)
            
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
            blink_yellow_purple()  # Start blinking umiddelbart etter STT (Anda tenker!)
            
            if not prompt:
                no_response_count += 1
                if no_response_count >= 2:
                    speak(messages_config['conversation']['no_response_timeout'], speech_config, beak)
                    break
                speak(messages_config['conversation']['no_response_retry'], speech_config, beak)
                continue
            
            # Reset teller når vi får svar
            no_response_count = 0
            
            # Check if we're in face learning workflow
            print(f"🔍 Before handle_name_response: _waiting_for_name={_waiting_for_name}, _waiting_for_confirmation={_waiting_for_confirmation}, prompt='{prompt}'", flush=True)
            if handle_name_response(prompt, speech_config, beak):
                # Name/confirmation handled, continue conversation loop
                print("🔍 handle_name_response returned True, continuing loop", flush=True)
                continue
            print("🔍 handle_name_response returned False, proceeding to ChatGPT", flush=True)
            
            # Sjekk om bruker vil bytte nettverk (trigger fra AI funksjon)
            if os.path.exists('/tmp/duck_switch_network.txt'):
                try:
                    os.remove('/tmp/duck_switch_network.txt')
                    print("🔄 Bytter til hotspot-modus...", flush=True)
                    
                    # Koble ned alle WiFi-connections først
                    import subprocess
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
                # Blinking startet allerede rett etter STT - fortsetter under AI-prosessering
                result = chatgpt_query(
                    messages, 
                    api_key, 
                    memory_manager=memory_manager, 
                    user_manager=user_manager,
                    sms_manager=sms_manager,
                    hunger_manager=hunger_manager,
                    vision_service=vision_service,
                    source="voice"
                )
                # LED fortsetter å blinke til speak() tar over (rød LED når lyd starter)
                
                # Håndter tuple-retur (svar, is_thank_you)
                if isinstance(result, tuple):
                    reply, is_thank_you = result
                else:
                    reply = result
                    is_thank_you = False
                
                # Håndter hvis chatgpt_query returnerte None (f.eks. ved API-feil)
                if reply is None:
                    raise Exception("ChatGPT returnerte None - sannsynligvis API-feil")
                
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
