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
from scripts.hardware.rgb_duck import set_blue, off, blink_yellow_purple, pulse_blue, pulse_yellow, stop_blink, set_yellow, blink_yellow
from src.duck_config import MESSAGES_FILE
from src.duck_memory import MemoryManager
from src.duck_user_manager import UserManager
from src.duck_audio import speak
from src.duck_speech import wait_for_wake_word, recognize_speech_from_mic
from src.duck_music import play_song
from src.duck_conversation import check_ai_queries, ask_for_user_switch, is_conversation_ending
from src.duck_event_bus import get_event_bus, Event
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

def set_idle_led():
    """Sett LED til riktig idle-farge: gul blinkende hvis hotspot, ellers blå."""
    if is_hotspot_active():
        blink_yellow()
    else:
        set_blue()


def set_sleep_led():
    """Sett LED til riktig sleep-farge: gul pulsering hvis hotspot, ellers blå pulsering."""
    if is_hotspot_active():
        pulse_yellow()
    else:
        pulse_blue()


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


def _send_duck_response(from_duck, message_text, media_url, messenger, sms_manager, fed=False, food_item_name=None):
    """Generate and send response to duck message (called after delay)"""
    from duck_services import get_services
    from duck_ai import chatgpt_query
    
    services = get_services()
    memory_manager = services.get_memory_manager()
    
    # Get recent conversation history (last 5 messages)
    recent_messages = messenger.get_conversation_history(from_duck, limit=5)
    
    # Build conversation context
    conversation_context = ""
    if recent_messages:
        conversation_context = "\n\nSiste meldinger i samtalen:\n"
        our_duck_name = os.getenv('DUCK_NAME', 'Samantha').lower()
        for msg in recent_messages:
            sender = "Du" if msg['from_duck'] == our_duck_name else msg['from_duck'].capitalize()
            conversation_context += f"{sender}: {msg['message']}\n"
    
    # Build context and generate response
    relation = messenger.get_duck_relation(from_duck)
    
    # Add feeding context if fed
    fed_context = ""
    if fed and food_item_name:
        fed_context = f"\n\n🍕 VIKTIG MAT-KONTEKST:\n{relation} ga deg akkurat MAT ({food_item_name})! Dette er MAT TIL DEG som and.\nDu ble matet og er glad!\nTakk dem for maten! F.eks: 'Takk for maten! Nam nam! 🦆' eller 'Åh, kjeks! Takk søster! 😋'"
    
    # Get some recent memories to share
    memories = memory_manager.search_memories("", limit=3)
    memory_hints = ""
    if memories and len(memories) > 0:
        memory_hints = "\n\nTing du kan dele fra dagen:\n"
        for mem, _ in memories[:3]:
            if hasattr(mem, 'text') and mem.text and len(mem.text) > 20:
                memory_hints += f"- {mem.text[:100]}\n"
    
    prompt = f"""Du fikk nettopp en melding fra {relation}:
"{message_text}"{conversation_context}

VIKTIG: Se på samtalehistorikken! Hvis dere bare sender tomme "takk for maten" eller generiske "håper du har det bra" frem og tilbake uten substans, IKKE SVAR. Skriv "NO_RESPONSE" i stedet.

Svar KUN hvis:
1. De spurte et spesifikt spørsmål du kan svare på
2. Du har noe NYTT og INTERESSANT å dele (en opplevelse, noe du så, noe som skjedde)
3. Du fikk mat og vil takke (men kort!)

Hvis du svarer, del gjerne:
- Noe morsomt/interessant du opplevde i dag
- Noe du lærte eller tenkte på
- Et spørsmål om DERES dag{memory_hints}{fed_context}

Skriv et kort, hyggelig svar (maks 160 tegn) ELLER skriv "NO_RESPONSE" hvis samtalen er tom."""
    
    messages_context = [{"role": "user", "content": prompt}]
    response_tuple = chatgpt_query(
        messages_context,
        api_key=os.getenv('OPENAI_API_KEY'),
        model="gpt-4o",
        enable_tools=False  # Disable tools for auto-response to avoid recursion
    )
    
    if response_tuple:
        response = response_tuple[0] if isinstance(response_tuple, tuple) else response_tuple
        
        # Check if AI decided not to respond
        if "NO_RESPONSE" in response or response.strip() == "NO_RESPONSE":
            print(f"🤐 AI besluttet å ikke svare {from_duck} (samtalen mangler substans)", flush=True)
            return
        
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
        
        # Post response event til main loop
        bus = get_event_bus()
        bus.post(Event.DUCK_RESPONSE, {
            'response': response,
            'to_duck': from_duck
        })
        
        # Save to memory
        memory_manager.save_message(
            user_text=message_text,
            ai_response=response,
            user_name=from_duck
        )


def sms_polling_loop():
    """Poll relay for new SMS messages and duck-to-duck messages every 10 seconds"""
    from src.duck_sms import SMSManager
    from src.duck_messenger import DuckMessenger
    from src.duck_services import get_services
    
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
    pending_duck_responses = []  # [(respond_at_time, from_duck, message_text, media_url, fed, food_item_name), ...]
    
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
        
        for respond_at, from_duck, message_text, media_url, fed, food_item_name in responses_to_send:
            try:
                print(f"⏰ Tid til å svare til {from_duck}!", flush=True)
                # Generate and send response
                _send_duck_response(from_duck, message_text, media_url, messenger, sms_manager, fed, food_item_name)
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
                                            
                                            # Post MMS SMS announcement event
                                            bus = get_event_bus()
                                            bus.post(Event.SMS_ANNOUNCEMENT, announcement)
                                            
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
                            from src.duck_services import get_services
                            from src.duck_audio import speak
                            
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
                                
                                # Post SMS announcement event
                                bus = get_event_bus()
                                bus.post(Event.SMS_ANNOUNCEMENT, announcement)
                                
                                # Send AI-generated response (AI will know if she was fed from context)
                                if result.get('should_respond'):
                                    response_result = sms_manager.generate_and_send_response(
                                        contact, message_text, fed=result.get('fed', False)
                                    )
                                    if response_result.get('status') == 'sent':
                                        response_text = response_result.get('message', '')
                                        print(f"📤 Sent response: {response_text[:50]}...", flush=True)
                                        # Post SMS response event
                                        bus = get_event_bus()
                                        bus.post(Event.SMS_RESPONSE, f"Jeg sendte svar: {response_text}")
                            
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
                    
                    # Check for food emojis - Seven kan mate Samantha!
                    from duck_services import get_services
                    from duck_hunger import FOOD_VALUES
                    services = get_services()
                    hunger_manager = services.get_hunger_manager()
                    
                    fed = False
                    food_item_name = None
                    for food_item in FOOD_VALUES.keys():
                        if food_item in message_text:
                            result = hunger_manager.feed(food_item)
                            if result['status'] == 'fed':
                                fed = True
                                food_item_name = food_item
                                print(f"😋 {from_duck} matet meg med {food_item}! Hunger: {result['new_level']}", flush=True)
                                break
                    
                    # Check for loop BEFORE scheduling response
                    if messenger.detect_loop(from_duck, message_text):
                        print(f"⚠️ Loop detektert med {from_duck}, hopper over SVAR (melding er logget)", flush=True)
                        continue
                    
                    # Random delay før svar (30 sek til 4 min) - legg til i køy
                    import random
                    delay_seconds = random.randint(30, 240)  # 30 sek til 4 min
                    respond_at = datetime.now() + timedelta(seconds=delay_seconds)
                    pending_duck_responses.append((respond_at, from_duck, message_text, media_url, fed, food_item_name))
                    print(f"⏱️ Planlagt svar til {from_duck} om {delay_seconds} sekunder (kl {respond_at.strftime('%H:%M:%S')})", flush=True)
                    
                    # Format announcement for immediate playback
                    announcement = messenger.format_incoming_announcement(from_duck, message_text)
                    
                    print(f"🦆💬 Message from {from_duck}: {message_text[:50]}...", flush=True)
                    
                    # Post duck message event
                    bus = get_event_bus()
                    bus.post(Event.DUCK_MESSAGE, {
                        'announcement': announcement,
                        'from_duck': from_duck,
                        'message': message_text,
                        'media_url': media_url
                    })
        except Exception as e:
            print(f"⚠️ Duck message polling error: {e}", flush=True)


def reminder_checker_loop():
    """Sjekker påminnelser og alarmer hver 30. sekund"""
    from src.duck_reminders import ReminderManager, REMINDER_TYPE_ALARM
    from src.duck_sleep import is_sleeping, disable_sleep
    from src.duck_memory import MemoryManager, Memory
    
    reminder_mgr = ReminderManager()
    memory_mgr = MemoryManager()
    
    while True:
        time.sleep(30)  # Sjekk hvert 30. sekund
        try:
            due = reminder_mgr.get_due_reminders()
            
            for reminder in due:
                announcement = reminder_mgr.format_announcement(reminder)
                is_alarm = reminder.get('reminder_type') == REMINDER_TYPE_ALARM
                
                # Hvis alarm og anda sover, vekk henne!
                if is_alarm and is_sleeping():
                    print(f"⏰ ALARM! Vekker anda fra sovemodus: {reminder['message']}", flush=True)
                    disable_sleep()
                
                # Post reminder event
                bus = get_event_bus()
                bus.post(Event.REMINDER, {
                    'announcement': announcement,
                    'reminder_id': reminder['id'],
                    'is_alarm': is_alarm,
                    'message': reminder['message']
                })
                
                type_str = "⏰ Alarm" if is_alarm else "🔔 Påminnelse"
                print(f"{type_str}: {reminder['message']}", flush=True)
                
                # Marker som annonsert
                reminder_mgr.mark_announced(reminder['id'])
                
                # Lagre i minnet at påminnelsen ble levert
                try:
                    type_name = "Alarm" if is_alarm else "Påminnelse"
                    user_name = reminder.get('user_name', 'Osmund')
                    memory_text = f"{type_name} levert til {user_name}: '{reminder['message']}'"
                    memory = Memory(
                        text=memory_text,
                        topic="påminnelser",
                        confidence=0.9,
                        source="reminder_system"
                    )
                    memory_mgr.save_memory(memory, user_name=user_name)
                    print(f"💾 Påminnelse lagret i minnet", flush=True)
                except Exception as e:
                    print(f"⚠️ Kunne ikke lagre påminnelse i minnet: {e}", flush=True)
                
                # Vent litt mellom flere påminnelser
                if len(due) > 1:
                    time.sleep(5)
                    
        except Exception as e:
            print(f"⚠️ Reminder check error: {e}", flush=True)


def boredom_timer_loop():
    """Increase boredom gradually every hour and check for triggers"""
    from src.duck_sms import SMSManager
    
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
                    from src.duck_config import MUSIKK_DIR
                    musikk_dir = MUSIKK_DIR
                    available_songs = [d for d in os.listdir(musikk_dir) 
                                     if os.path.isdir(os.path.join(musikk_dir, d)) and 
                                     os.path.exists(os.path.join(musikk_dir, d, "duck_mix.wav"))]
                    
                    if available_songs:
                        random_song = random.choice(available_songs)
                        song_folder = os.path.join(musikk_dir, random_song)
                        
                        print(f"🎵 Anda kjeder seg (level {new_level:.1f}) - synger {random_song}", flush=True)
                        
                        # Annonser kjedsomhet + sang i én melding
                        if ' - ' in random_song:
                            artist, song_title = random_song.split(' - ', 1)
                            announcement = f"Jeg kjeder meg litt, så nå skal jeg synge {song_title} av {artist}!"
                        else:
                            announcement = f"Jeg kjeder meg litt, så jeg skal synge {random_song}!"
                        bus = get_event_bus()
                        bus.post(Event.SONG_ANNOUNCEMENT, announcement)
                        
                        # Spill sangen uten ekstra annonsering
                        play_song(song_folder, beak, speech_config, announce=False)
                        
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
                        
                        # Post boredom SMS announcement event
                        announcement = f"Jeg sendte en melding til {contact['name']} fordi jeg kjeder meg."
                        bus = get_event_bus()
                        bus.post(Event.SMS_ANNOUNCEMENT, announcement)
                    elif result.get('status') == 'no_contact':
                        print("😔 Ingen kontakter tilgjengelig for kjed-melding", flush=True)
        except Exception as e:
            print(f"⚠️ Boredom timer error: {e}", flush=True)


def hunger_timer_loop():
    """Manage hunger system - Tamagotchi style!"""
    from src.duck_services import get_services
    
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
                
                # Post hunger announcement event
                bus = get_event_bus()
                bus.post(Event.HUNGER_ANNOUNCEMENT, announcement)
                
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


# Siste stemmegjenkjenning fra Duck-Vision (brukes som fallback ved wake word)
_last_speaker_name = None
_last_speaker_confidence = 0.0
_last_speaker_time = 0.0

# Mid-conversation stemmegjenkjenning
_conversation_active = False
_mid_conversation_speaker = None  # Navn gjenkjent under pågående samtale
_mid_conversation_announced = False  # Har vi allerede sagt hei?

# Onboarding av ukjent person (voice learning)
_onboarding_voice_active = False
_onboarding_voice_event = threading.Event()
_onboarding_voice_success = False

def on_speaker_recognized(name: str, confidence: float):
    """Callback når Duck-Vision gjenkjenner en stemme i bakgrunnen"""
    global _last_speaker_name, _last_speaker_confidence, _last_speaker_time
    global _mid_conversation_speaker
    _last_speaker_name = name
    _last_speaker_confidence = confidence
    _last_speaker_time = time.time()
    print(f"🔊 Stemme gjenkjent: {name} ({confidence:.0%})", flush=True)
    
    # Hvis samtale pågår og vi ikke har identifisert noen ennå, lagre for bruk i loop
    if _conversation_active and not _mid_conversation_announced:
        _mid_conversation_speaker = name
        print(f"💬 Mid-conversation stemme: {name} - vil oppdatere bruker i samtaleloop", flush=True)


def on_voice_learned(name: str, success: bool):
    """Callback når Duck-Vision har opprettet en stemmeprofil"""
    global _onboarding_voice_success
    
    # Hvis vi er i onboarding-modus, signal til onboarding-funksjonen
    if _onboarding_voice_active:
        _onboarding_voice_success = success
        _onboarding_voice_event.set()
        if success:
            print(f"✅ Onboarding: Stemmeprofil opprettet for {name}", flush=True)
        else:
            print(f"❌ Onboarding: Stemmeprofil feilet for {name}", flush=True)
        return
    
    # Normal oppførsel (automatisk stemmeprofil i bakgrunnen)
    if success:
        print(f"✅ Stemmeprofil opprettet for {name}", flush=True)
        try:
            if hasattr(on_learning_progress, 'speech_config') and hasattr(on_learning_progress, 'beak'):
                from src.duck_audio import speak
                speak(f"Nå kjenner jeg også stemmen din, {name}!", on_learning_progress.speech_config, on_learning_progress.beak)
                # Sett LED tilbake til idle-modus etter speak
                set_idle_led()
        except Exception as e:
            print(f"⚠️ Kunne ikke si stemmeprofil-beskjed: {e}", flush=True)
    else:
        print(f"❌ Kunne ikke opprette stemmeprofil for {name}", flush=True)


def extract_name_from_response(text: str) -> str:
    """Ekstraher et personnavn fra et naturlig språk-svar.
    
    Håndterer svar som 'Arvid', 'Jeg heter Arvid', 'Det er Arvid', etc.
    """
    text = text.strip().rstrip('.,!?')
    
    # Fjern vanlige norske og engelske prefiks
    prefixes = [
        "jeg heter ", "mitt navn er ", "det er ", "navnet mitt er ",
        "de kaller meg ", "jeg er ", "folk kaller meg ",
        "my name is ", "i am ", "i'm ", "it's ", "call me ",
    ]
    text_lower = text.lower()
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # Fjern ev. fyllord på slutten
    suffixes = [" da", " altså", " liksom", " ass", " vet du", " skjønner du"]
    for suffix in suffixes:
        if text.lower().endswith(suffix):
            text = text[:-len(suffix)].strip()
            break
    
    # Ta maks 2 ord (fornavn + eventuelt etternavn), kapitaliser
    words = text.split()
    if not words:
        return ""
    
    name_words = words[:2] if len(words) <= 3 else words[:1]
    return ' '.join(w.capitalize() for w in name_words)


def handle_unknown_person_onboarding(speech_config, beak, vision_service, user_manager):
    """Spør ukjent person om navn og samtykke til å huske stemme/ansikt.
    
    Kalles etter en naturlig samtaleslutt med en ugjenkjent person.
    Returns: Personens navn hvis onboarding lykkes, None ellers.
    """
    global _onboarding_voice_active, _onboarding_voice_success
    
    from src.duck_audio import speak
    from src.duck_speech import recognize_speech_from_mic
    
    print("🤝 Starter onboarding av ukjent person", flush=True)
    
    positive_words = ["ja", "jada", "selvfølgelig", "klart", "ok", "okei", 
                      "greit", "gjerne", "absolutt", "sikkert", "sure", "yes",
                      "det kan du", "det er greit", "kjør på", "fint"]
    
    # Steg 1: Spør om navn
    speak("Forresten, vi har ikke blitt ordentlig kjent ennå! Hva heter du?",
          speech_config, beak)
    
    name_response = recognize_speech_from_mic()
    if not name_response:
        speak("Jeg hørte deg ikke, men hyggelig å snakke med deg!",
              speech_config, beak)
        set_idle_led()
        return None
    
    name = extract_name_from_response(name_response)
    if not name or len(name) < 2:
        speak("Beklager, jeg fikk ikke med meg navnet. Men hyggelig å snakke med deg!",
              speech_config, beak)
        set_idle_led()
        return None
    
    print(f"🤝 Ekstrahert navn: '{name}' fra svar: '{name_response}'", flush=True)
    
    # Steg 2: Spør om samtykke til å huske stemme
    speak(f"Hyggelig å møte deg, {name}! Er det greit at jeg husker stemmen din, "
          f"så jeg kjenner deg igjen neste gang?", speech_config, beak)
    
    consent_response = recognize_speech_from_mic()
    if not consent_response:
        speak(f"Ingen problem! Hyggelig å snakke med deg, {name}!",
              speech_config, beak)
        set_idle_led()
        return name
    
    consent_lower = consent_response.lower()
    if not any(word in consent_lower for word in positive_words):
        speak(f"Helt i orden, {name}! Hyggelig å snakke med deg!",
              speech_config, beak)
        set_idle_led()
        return name
    
    # Steg 3: Lagre stemmeprofil fra samtaledata
    # Duck-Vision har allerede samlet stemmedata under samtalen.
    # Vi bruker save_conversation_voice som lager profil fra det som allerede er samlet.
    # VIKTIG: notify_conversation(False) må IKKE ha blitt kalt ennå, ellers er audioen slettet.
    
    _onboarding_voice_active = True
    _onboarding_voice_event.clear()
    _onboarding_voice_success = False
    
    voice_learning_ok = False
    if vision_service and vision_service.is_connected():
        vision_service.save_conversation_voice(name)
        print(f"🎤 Sendt save_conversation_voice for {name}", flush=True)
        
        # Vent på resultat (profilen lages fra allerede samlet audio, bør gå raskt)
        got_result = _onboarding_voice_event.wait(timeout=10.0)
        if got_result and _onboarding_voice_success:
            voice_learning_ok = True
    
    _onboarding_voice_active = False
    
    if voice_learning_ok:
        speak(f"Flott, {name}! Nå husker jeg stemmen din.", speech_config, beak)
        print(f"✅ Onboarding ferdig: {name} - stemmeprofil OK", flush=True)
    else:
        speak(f"Hyggelig å møte deg, {name}! "
              f"Jeg klarte dessverre ikke å lagre stemmen din denne gangen, men vi prøver igjen neste gang!",
              speech_config, beak)
        print(f"⚠️ Onboarding: stemmelæring feilet for {name}", flush=True)
    
    # Steg 4: Spør om ansiktslæring
    if vision_service and vision_service.is_connected():
        speak(f"Vil du at jeg også skal kunne kjenne deg igjen på utseendet? "
              f"Da tar jeg noen raske bilder.", speech_config, beak)
        
        face_response = recognize_speech_from_mic()
        if face_response and any(word in face_response.lower() for word in positive_words):
            speak("Fint! Se mot meg, og beveg hodet litt mellom bildene.", speech_config, beak)
            try:
                vision_service.learn_person(name, num_samples=5)
                # Vent på at bildene tas (5 bilder * ~2.5s + buffer)
                time.sleep(15)
                speak(f"Perfekt, {name}! Nå kjenner jeg både stemmen og ansiktet ditt!", speech_config, beak)
                print(f"✅ Ansiktslæring fullført for {name}", flush=True)
            except Exception as e:
                print(f"⚠️ Ansiktslæring feilet for {name}: {e}", flush=True)
                speak(f"Hmm, bildene ble ikke helt bra, men stemmen din har jeg i alle fall!", speech_config, beak)
        else:
            speak(f"Ingen problem! Stemmen din er nok til at jeg kjenner deg igjen.", speech_config, beak)
    
    # Registrer brukeren i user_manager
    if user_manager:
        try:
            user_manager.switch_user(name, name, 'new_person')
            print(f"✅ Registrert ny bruker: {name}", flush=True)
        except Exception as e:
            print(f"⚠️ Kunne ikke registrere ny bruker {name}: {e}", flush=True)
    
    set_idle_led()
    return name


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
    # Rydd opp gammel event-bus ved oppstart
    from src.duck_event_bus import get_event_bus, Event
    bus = get_event_bus()
    bus.clear()
    
    # Prøv å initialisere servo, men fortsett uten hvis den ikke finnes
    beak = None
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        print("Servo initialisert OK", flush=True)
    except Exception as e:
        print(f"Advarsel: Kunne ikke initialisere servo (fortsetter uten): {e}", flush=True)
        beak = None
    
    # Initialiser DuckSettings (thread-safe in-memory settings)
    from src.duck_settings import get_settings, start_settings_server
    settings = get_settings()
    settings.load_from_tmp_files()
    start_settings_server()

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
    
    # Start reminder checker thread
    reminder_thread = threading.Thread(target=reminder_checker_loop, daemon=True)
    reminder_thread.start()
    print("✅ Reminder checker started (checks every 30 seconds)", flush=True)
    
    # Start hunger timer thread
    hunger_timer_thread = threading.Thread(target=hunger_timer_loop, daemon=True)
    hunger_timer_thread.start()
    print("✅ Hunger timer started (Tamagotchi mode activated! 🍪🍕)", flush=True)
    
    # Initialize 3D printer manager (on-demand monitoring - activated via voice or control panel)
    try:
        from src.duck_prusa import get_prusa_manager
        
        prusa = get_prusa_manager()
        if prusa.is_configured():
            print("✅ 3D printer configured (on-demand monitoring - say 'skru på 3D-printeren' to activate)", flush=True)
        else:
            print("ℹ️ 3D printer not configured (PRUSALINK_API_KEY/PRUSALINK_HOST missing)", flush=True)
    except Exception as e:
        print(f"⚠️ 3D printer init feilet: {e}", flush=True)
    
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
                on_learning_progress=on_learning_progress,
                on_speaker_recognized=on_speaker_recognized,
                on_voice_learned=on_voice_learned
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
    from src.duck_config import BASE_PATH
    hotspot_announcement_file = '/tmp/duck_hotspot_announcement.txt'
    hotspot_audio_file = os.path.join(BASE_PATH, 'audio', 'hotspot_announcement.wav')
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
                # Sett LED til gul blinkende for hotspot-modus
                blink_yellow()
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
    if not hotspot_active and not is_hotspot_active():
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
    elif is_hotspot_active() and not hotspot_active:
        print("📡 Hotspot aktiv - hopper over TTS-hilsen (krever internett)", flush=True)
        greeting_success = True  # Ikke blokkér oppstart
    
    if not greeting_success:
        print("Oppstartshilsen/hotspot-melding kunne ikke sies etter 3 forsøk - fortsetter uten hilsen", flush=True)
    
    # Sett idle LED basert på hotspot-status
    set_idle_led()
    if is_hotspot_active():
        print("📡 Hotspot er aktivt - LED blinker gult", flush=True)
    
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
            # Start pulsering bare én gang (gul hvis hotspot, blå ellers)
            if not sleep_led_active:
                set_sleep_led()
                hotspot_str = " + hotspot" if is_hotspot_active() else ""
                print(f"💤 Sleep mode aktiv{hotspot_str} - pulserer LED", flush=True)
                sleep_led_active = True
            
            # Sjekk events fra event bus SELV I SØVNMODUS
            bus = get_event_bus()
            for event_type, data in bus.drain():
                try:
                    if event_type == Event.SMS_ANNOUNCEMENT:
                        print(f"📬 [SLEEP MODE] SMS announcement: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.SMS_RESPONSE:
                        print(f"📤 [SLEEP MODE] SMS response: {str(data)[:50]}...", flush=True)
                        time.sleep(0.5)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.DUCK_MESSAGE:
                        announcement = data.get('announcement') if isinstance(data, dict) else data
                        if announcement:
                            print(f"🦆💬 [SLEEP MODE] Duck message: {announcement[:50]}...", flush=True)
                            speak(announcement, speech_config, beak)
                            set_sleep_led()
                    elif event_type == Event.DUCK_RESPONSE:
                        response = data.get('response') if isinstance(data, dict) else data
                        if response:
                            print(f"🦆📤 [SLEEP MODE] Duck response: {response[:50]}...", flush=True)
                            speak(response, speech_config, beak)
                            set_sleep_led()
                    elif event_type == Event.SONG_ANNOUNCEMENT:
                        print(f"🎵 [SLEEP MODE] Song announcement: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.PLAY_SONG:
                        song_path = data.get('path') if isinstance(data, dict) else data
                        should_announce = data.get('announce', True) if isinstance(data, dict) else True
                        if song_path and os.path.exists(song_path):
                            print(f"🎵 [SLEEP MODE] Playing song: {song_path} (announce={should_announce})", flush=True)
                            play_song(song_path, beak, speech_config, announce=should_announce)
                            set_sleep_led()
                    elif event_type == Event.HUNGER_ANNOUNCEMENT:
                        print(f"😋 [SLEEP MODE] Hunger announcement: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.HUNGER_FED:
                        print(f"😋 [SLEEP MODE] Fed from panel: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.HOTSPOT_ANNOUNCEMENT:
                        print(f"📡 [SLEEP MODE] Hotspot announcement: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.PRUSA_ANNOUNCEMENT:
                        print(f"🖨️ [SLEEP MODE] Prusa announcement: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.REMINDER:
                        announcement = data.get('announcement') if isinstance(data, dict) else data
                        is_alarm = data.get('is_alarm', False) if isinstance(data, dict) else False
                        if announcement:
                            if is_alarm:
                                print(f"⏰ [SLEEP MODE → WAKE] Alarm: {announcement[:50]}...", flush=True)
                            else:
                                print(f"🔔 [SLEEP MODE] Reminder: {announcement[:50]}...", flush=True)
                            speak(announcement, speech_config, beak)
                            if not is_alarm:
                                set_sleep_led()
                    elif event_type == Event.EXTERNAL_MESSAGE:
                        print(f"💬 [SLEEP MODE] External message: {str(data)[:50]}...", flush=True)
                        speak(data, speech_config, beak)
                        set_sleep_led()
                    elif event_type == Event.SWITCH_NETWORK:
                        print(f"🔄 [SLEEP MODE] Network switch ignored in sleep mode", flush=True)
                except Exception as e:
                    print(f"⚠️ Error handling sleep event {event_type}: {e}", flush=True)
            
            # Vent 0.5 sekunder før vi sjekker igjen (for rask respons)
            time.sleep(0.5)
            continue
        else:
            # Reset flag når ikke i sleep mode
            if sleep_led_active:
                stop_blink()
                set_idle_led()  # Gul blinkende hvis hotspot, ellers blå
                sleep_led_active = False
                print("⏰ Sleep mode deaktivert - våkner opp", flush=True)
        
        # Sjekk events fra bus UTENFOR sleep mode (før wake word)
        bus = get_event_bus()
        pre_wake_event = None
        for event_type, data in bus.drain():
            try:
                if event_type == Event.PLAY_SONG:
                    song_path = data.get('path') if isinstance(data, dict) else data
                    should_announce = data.get('announce', True) if isinstance(data, dict) else True
                    if song_path and os.path.exists(song_path):
                        print(f"🎵 Playing song from request: {song_path} (announce={should_announce})", flush=True)
                        play_song(song_path, beak, speech_config, announce=should_announce)
                elif event_type == Event.PRUSA_ANNOUNCEMENT:
                    print(f"🖨️ Prusa announcement: {str(data)[:50]}...", flush=True)
                    speak(data, speech_config, beak)
                elif event_type == Event.REMINDER:
                    announcement = data.get('announcement') if isinstance(data, dict) else data
                    is_alarm = data.get('is_alarm', False) if isinstance(data, dict) else False
                    if announcement:
                        emoji = "⏰" if is_alarm else "🔔"
                        print(f"{emoji} Reminder announcement: {announcement[:50]}...", flush=True)
                        speak(announcement, speech_config, beak)
                elif event_type in (Event.SMS_ANNOUNCEMENT, Event.SMS_RESPONSE, Event.DUCK_MESSAGE,
                                     Event.DUCK_RESPONSE, Event.SONG_ANNOUNCEMENT, Event.HUNGER_ANNOUNCEMENT,
                                     Event.HUNGER_FED, Event.HOTSPOT_ANNOUNCEMENT):
                    # Speak these directly (they would otherwise be caught in wake word loop)
                    text = data.get('announcement', data) if isinstance(data, dict) else data
                    if isinstance(data, dict) and 'response' in data:
                        text = data['response']
                    print(f"📢 Event {event_type.name}: {str(text)[:50]}...", flush=True)
                    speak(text, speech_config, beak)
                elif event_type == Event.EXTERNAL_MESSAGE:
                    # Pass to main loop as external_message
                    pre_wake_event = data
                elif event_type == Event.SWITCH_NETWORK:
                    pre_wake_event = '__SWITCH_NETWORK__'
            except Exception as e:
                print(f"⚠️ Error handling pre-wake event {event_type}: {e}", flush=True)
        
        if pre_wake_event:
            external_message = pre_wake_event
        else:
            # Normal wake word detection (nå uten fil-sjekking)
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
        vision_recognized = False
        voice_recognized = False
        conversation_ended_naturally = False
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
                
                # Sjekk om det er en respons-annonsering via event bus
                time.sleep(1)
                bus = get_event_bus()
                response_event = bus.get_nowait()
                if response_event and response_event[0] == Event.SMS_RESPONSE:
                    time.sleep(0.5)
                    speak(response_event[1], speech_config, beak)
                elif response_event:
                    # Put back non-SMS_RESPONSE event
                    bus.post(response_event[0], response_event[1])
                continue  # Gå tilbake til wake word etter SMS
            elif external_message.startswith('__DUCK_MESSAGE__'):
                # Duck-to-duck message announcement
                announcement = external_message.replace('__DUCK_MESSAGE__', '', 1)
                speak(announcement, speech_config, beak)
                
                # Sjekk om det er en respons-annonsering via event bus
                time.sleep(1)
                bus = get_event_bus()
                response_event = bus.get_nowait()
                if response_event and response_event[0] == Event.DUCK_RESPONSE:
                    response = response_event[1].get('response') if isinstance(response_event[1], dict) else response_event[1]
                    if response:
                        time.sleep(0.5)
                        speak(response, speech_config, beak)
                elif response_event:
                    # Put back non-DUCK_RESPONSE event
                    bus.post(response_event[0], response_event[1])
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
            elif external_message.startswith('__REMINDER__'):
                # Påminnelse/alarm announcement
                announcement = external_message.replace('__REMINDER__', '', 1)
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
            # Normal wake word - signal samtalestart til Duck-Vision
            global _conversation_active, _mid_conversation_speaker, _mid_conversation_announced
            _conversation_active = True
            _mid_conversation_speaker = None
            _mid_conversation_announced = False
            if vision_service and vision_service.is_connected():
                vision_service.notify_conversation(True)
            
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
            voice_recognized = False
            if vision_service and vision_service.is_connected():
                try:
                    found, name, confidence = vision_service.check_person(timeout=2.0)
                    
                    if found and name:
                        # Map face recognition name to memory system name
                        mapped_name = face_name_mapping.get(name, name)
                        print(f"👋 Gjenkjent {name} ({confidence:.2%}) -> mapped to {mapped_name}", flush=True)
                        user_name = mapped_name
                        vision_recognized = True
                    else:
                        # Unknown or no person - try voice recognition as fallback
                        voice_recognized = False
                        # Sjekk om vi har en fersk stemmegjenkjenning (siste 30 sek)
                        if _last_speaker_name and (time.time() - _last_speaker_time) < 30.0:
                            mapped_voice = face_name_mapping.get(_last_speaker_name, _last_speaker_name)
                            print(f"🔊 Stemme-fallback: {_last_speaker_name} ({_last_speaker_confidence:.0%}) -> {mapped_voice}", flush=True)
                            user_name = mapped_voice
                            voice_recognized = True
                        
                        if not voice_recognized:
                            print(f"👤 Ukjent person (hverken ansikt eller stemme) - bruker fallback: {user_name}", flush=True)
                    
                except Exception as e:
                    print(f"⚠️ Error checking person: {e}", flush=True)
            else:
                print("⚠️ Duck-Vision not available or not connected", flush=True)
            
            # Generer adaptiv hilsen basert på personlighetsprofil
            if vision_recognized:
                # Enklere hilsen når face recognition gjenkjenner
                greeting_msg = f"Hei, {user_name}! Hyggelig å se deg igjen!"
                print(f"🎭 Face recognition greeting: {greeting_msg}", flush=True)
            elif voice_recognized:
                # Gjenkjent via stemme - litt annerledes hilsen
                greeting_msg = f"Hei, {user_name}! Jeg kjente deg igjen på stemmen!"
                print(f"🎭 Voice recognition greeting: {greeting_msg}", flush=True)
            else:
                # Ikke gjenkjent - bruk generisk hilsen uten navn
                greeting_msg = get_adaptive_greeting(user_name="du")
                print(f"🎭 Generic greeting (ukjent person): {greeting_msg}", flush=True)
            
            speak(greeting_msg, speech_config, beak)
        
        # Reduce boredom when conversation starts
        try:
            from src.duck_sms import SMSManager
            sms_manager = SMSManager()
            sms_manager.reduce_boredom(amount=2.0)
        except Exception as e:
            print(f"⚠️ Could not reduce boredom: {e}", flush=True)
        
        # Start samtale (enten fra wake word eller samtale-trigger)
        messages = []
        no_response_count = 0  # Teller antall ganger uten svar
        
        while True:
            # Sjekk om Duck-Vision har gjenkjent en stemme mid-conversation
            if _mid_conversation_speaker and not _mid_conversation_announced:
                _mid_conversation_announced = True
                _name_mapping = {'åsmund': 'Osmund', 'Åsmund': 'Osmund'}
                mid_name = _name_mapping.get(_mid_conversation_speaker, _mid_conversation_speaker)
                if not vision_recognized and not voice_recognized:
                    # Vi visste ikke hvem det var - nå vet vi!
                    user_name = mid_name
                    voice_recognized = True  # Marker som gjenkjent så onboarding ikke trigges
                    print(f"💬 Mid-conversation gjenkjenning: {_mid_conversation_speaker} -> {mid_name}", flush=True)
                    
                    # Bytt til gjenkjent bruker som aktiv bruker
                    if user_manager:
                        try:
                            user_manager.switch_user(mid_name, mid_name, 'recognized')
                            print(f"✅ Byttet aktiv bruker til {mid_name}", flush=True)
                        except Exception as e:
                            print(f"⚠️ Kunne ikke bytte bruker mid-conversation: {e}", flush=True)
                    
                    speak(f"Å, hei {mid_name}! Nå kjente jeg deg igjen på stemmen!", speech_config, beak)
            
            prompt = recognize_speech_from_mic()
            blink_yellow_purple()  # Start blinking umiddelbart etter STT (Anda tenker!)
            
            if not prompt:
                no_response_count += 1
                if no_response_count >= 2:
                    speak(messages_config['conversation']['no_response_timeout'], speech_config, beak)
                    # Signal samtaleslutt til Duck-Vision
                    _conversation_active = False
                    if vision_service and vision_service.is_connected():
                        vision_service.notify_conversation(False)
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
            
            # Sjekk om bruker vil bytte nettverk (trigger fra AI via event bus)
            bus = get_event_bus()
            switch_event = bus.get_nowait()
            if switch_event and switch_event[0] == Event.SWITCH_NETWORK:
                try:
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
                    subprocess.Popen([os.path.join(BASE_PATH, 'scripts', 'auto-hotspot.sh')])
                    
                    print("✅ Auto-hotspot startet!", flush=True)
                    
                except Exception as e:
                    print(f"⚠️ Kunne ikke bytte til hotspot: {e}", flush=True)
            elif switch_event:
                # Put back any non-SWITCH_NETWORK event
                bus.post(switch_event[0], switch_event[1])
            
            # Sjekk om bruker vil avslutte samtalen
            should_end_conversation = is_conversation_ending(prompt)
            
            # Avslutt umiddelbart hvis brukeren sier en avslutningsfrase
            if should_end_conversation:
                print("🔚 Samtale avsluttet (bruker sa avslutningsfrase)", flush=True)
                conversation_ended_naturally = True
                _conversation_active = False
                off()
                break
            
            # Sjekk for direkte bytte til eier/Osmund
            prompt_lower = prompt.strip().lower()
            if user_manager and ("bytt til eier" in prompt_lower or "bytte til eier" in prompt_lower or 
                                  "bytt til osmund" in prompt_lower or "bytte til osmund" in prompt_lower):
                current_user = user_manager.get_current_user()
                if current_user['username'] != 'Osmund':
                    user_manager.switch_user('Osmund', 'Osmund', 'owner')
                    speak("Velkommen tilbake Osmund!", speech_config, beak)
                    print(f"✅ Byttet tilbake til eier: Osmund", flush=True)
                    _conversation_active = False
                    if vision_service and vision_service.is_connected():
                        vision_service.notify_conversation(False)
                    break  # Start ny samtale
                else:
                    speak("Du er allerede Osmund, eieren!", speech_config, beak)
                    continue
            
            # Sjekk for brukerbytte-kommando
            if user_manager and ("bytt bruker" in prompt_lower or "skifte bruker" in prompt_lower or "bytte bruker" in prompt_lower):
                if ask_for_user_switch(speech_config, beak, user_manager):
                    # Vellykket brukerbytte - start ny samtale
                    _conversation_active = False
                    if vision_service and vision_service.is_connected():
                        vision_service.notify_conversation(False)
                    break
                else:
                    # Mislykket - fortsett samtale
                    continue
            
            messages.append({"role": "user", "content": prompt})
            
            # Sliding window: behold maks 20 meldinger for å spare tokens
            # Memory worker har allerede lagret viktige fakta fra eldre meldinger
            MAX_CONVERSATION_MESSAGES = 20
            if len(messages) > MAX_CONVERSATION_MESSAGES:
                messages = messages[-MAX_CONVERSATION_MESSAGES:]
            
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
                
                # Håndter tuple-retur (svar, is_thank_you, force_end)
                force_end = False
                if isinstance(result, tuple):
                    if len(result) == 3:
                        reply, is_thank_you, force_end = result
                    else:
                        reply, is_thank_you = result
                else:
                    reply = result
                    is_thank_you = False
                
                # Håndter hvis chatgpt_query returnerte None (f.eks. ved API-feil)
                if reply is None:
                    print("⚠️ ChatGPT returnerte None - sannsynligvis API-feil", flush=True)
                    reply = "Beklager, jeg fikk en feil fra AI-tjenesten. Kan du prøve å spørre igjen?"
                    is_thank_you = False
                    force_end = False
                
                # Sjekk om AI har markert samtalen som ferdig
                reply_upper = reply.upper()
                ai_wants_to_end = "[AVSLUTT]" in reply_upper or " AVSLUTT" in reply_upper or reply_upper.endswith("AVSLUTT")
                
                # Sjekk om AI-svaret inneholder typiske avslutningsfraser
                # (AI glemmer ofte [AVSLUTT] men bruker farvel-språk)
                if not ai_wants_to_end:
                    reply_lower = reply.lower()
                    ai_farewell_phrases = ["vi snakkes", "ha det bra", "kvakk for nå", "bare si ifra"]
                    if any(phrase in reply_lower for phrase in ai_farewell_phrases):
                        ai_wants_to_end = True
                
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
                if force_end:
                    print("🔚 Samtale tvunget avsluttet (enable_sleep_mode el.l.)", flush=True)
                    _conversation_active = False
                    if vision_service and vision_service.is_connected():
                        vision_service.notify_conversation(False)
                    break
                elif ai_wants_to_end:
                    print("🔚 Samtale avsluttet av AI", flush=True)
                    conversation_ended_naturally = True
                    _conversation_active = False
                    break
                elif is_thank_you:
                    print("🔚 Samtale avsluttet (bruker takket)", flush=True)
                    conversation_ended_naturally = True
                    _conversation_active = False
                    break
            except Exception as e:
                off()
                print("Feil:", e)
                speak("Beklager, det oppstod en feil.", speech_config, beak)
            
            set_idle_led()  # Gul blinkende hvis hotspot, ellers blå
        
        # Etter samtale: sjekk om vi bør spørre ukjent person om å bli kjent
        # Krav: naturlig samtaleslutt, personen er ukjent, minst 3 meldingsutvekslinger (6 meldinger)
        if (conversation_ended_naturally 
                and not vision_recognized 
                and not voice_recognized 
                and not _mid_conversation_announced
                and len(messages) >= 6):
            print(f"🤝 Ukjent person etter {len(messages)} meldinger - spør om onboarding", flush=True)
            try:
                handle_unknown_person_onboarding(speech_config, beak, vision_service, user_manager)
            except Exception as e:
                print(f"⚠️ Feil i onboarding: {e}", flush=True)
        
        # Send conversation end til Duck-Vision (frigjør audio-buffer)
        # Gjøres ETTER onboarding så save_conversation_voice har tilgang til audioen
        if conversation_ended_naturally and vision_service and vision_service.is_connected():
            vision_service.notify_conversation(False)


if __name__ == "__main__":
    main()
