"""
Duck Conversation Module
Handles conversation flow, user switching, and external message checks.
"""

import os
import time
from src.duck_config import AI_QUERY_FILE, AI_RESPONSE_FILE
from src.duck_speech import recognize_speech_from_mic
from src.duck_audio import speak


def check_ai_queries(api_key, speech_config, beak, memory_manager=None, user_manager=None, sms_manager=None, hunger_manager=None, vision_service=None):
    """
    Bakgrunnstråd som sjekker for AI-queries fra kontrollpanelet.
    Kjører kontinuerlig og prosesserer queries når de dukker opp.
    """
    from src.duck_ai import chatgpt_query  # Import her for å unngå circular import
    
    while True:
        try:
            if os.path.exists(AI_QUERY_FILE):
                with open(AI_QUERY_FILE, 'r', encoding='utf-8') as f:
                    query = f.read().strip()
                
                # Slett filen umiddelbart etter lesing for å unngå gjentakelse
                os.remove(AI_QUERY_FILE)
                
                if query:
                    print(f"AI-query fra kontrollpanel: {query}", flush=True)
                    
                    # Spør ChatGPT
                    messages = [{"role": "user", "content": query}]
                    response = chatgpt_query(
                        messages, 
                        api_key, 
                        memory_manager=memory_manager, 
                        user_manager=user_manager,
                        sms_manager=sms_manager,
                        hunger_manager=hunger_manager,
                        vision_service=vision_service,
                        source="voice"
                    )
                    
                    # Håndter tuple response
                    if isinstance(response, tuple):
                        response_text = response[0]
                    else:
                        response_text = response
                    
                    # Skriv respons til fil
                    with open(AI_RESPONSE_FILE, 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    
                    # Si svaret
                    speak(response_text, speech_config, beak)
                    
                    print(f"AI-respons: {response_text}", flush=True)
        except Exception as e:
            print(f"Feil i AI-query tråd: {e}", flush=True)
        
        time.sleep(0.5)  # Sjekk hver halve sekund


def ask_for_user_switch(speech_config, beak, user_manager):
    """
    Håndter brukerbytte-dialog med stemmebasert interaksjon.
    
    Args:
        speech_config: Azure speech config for TTS
        beak: Beak objekt for nebb-kontroll
        user_manager: UserManager instans
    
    Returns:
        True hvis brukeren ble byttet vellykket, False ellers
    """
    try:
        # Spør hvem som snakker
        speak("Hvem er du?", speech_config, beak)
        
        name_response = recognize_speech_from_mic()
        if not name_response:
            speak("Jeg hørte ikke navnet ditt. Prøv igjen ved å si mitt navn først.", speech_config, beak)
            return False
        
        # Sjekk om brukeren vil bytte til eier (Osmund)
        name_lower = name_response.strip().lower()
        if 'eier' in name_lower or 'owner' in name_lower:
            # Bytt direkte til Osmund
            user_manager.switch_user('Osmund', 'Osmund', 'owner')
            speak("Velkommen tilbake Osmund!", speech_config, beak)
            print(f"✅ Byttet tilbake til eier: Osmund", flush=True)
            return True
        
        # Ekstraher navnet (fjern "jeg er", "dette er", etc.)
        name_clean = name_response.strip().lower()
        name_clean = name_clean.replace("jeg er ", "").replace("dette er ", "").replace("jeg heter ", "")
        # Fjern punktum og andre tegn som kan legges til av stemmegjenkjenning
        name_clean = name_clean.rstrip('.!?,;:')
        name_clean = name_clean.strip().title()  # Kapitalisér første bokstav
        
        print(f"👤 Bruker sa navnet: {name_clean}", flush=True)
        
        # Søk etter bruker i database
        found_user = user_manager.find_user_by_name(name_clean)
        
        if found_user:
            # Bruker funnet - bekreft
            relation_text = found_user['relation']
            if found_user['matched_key']:
                speak(f"Er du {found_user['display_name']}, Osmunds {relation_text}?", speech_config, beak)
            else:
                speak(f"Er du {found_user['display_name']}?", speech_config, beak)
            
            confirmation = recognize_speech_from_mic()
            if confirmation and ('ja' in confirmation.lower() or 'stemmer' in confirmation.lower() or 'riktig' in confirmation.lower()):
                # Bytt bruker
                user_manager.switch_user(
                    username=found_user['username'],
                    display_name=found_user['display_name'],
                    relation=found_user['relation']
                )
                
                speak(f"Velkommen {found_user['display_name']}! Hva kan jeg hjelpe deg med?", speech_config, beak)
                print(f"✅ Byttet til bruker: {found_user['display_name']}", flush=True)
                return True
            else:
                speak("Beklager, da misforsto jeg. Prøv igjen.", speech_config, beak)
                return False
        else:
            # Ny bruker - spør om relasjon
            speak(f"Hei {name_clean}! Jeg kjenner deg ikke fra før. Hva er din relasjon til Osmund?", speech_config, beak)
            
            relation_response = recognize_speech_from_mic()
            if not relation_response:
                speak("Jeg hørte ikke hva du sa. Prøv igjen senere.", speech_config, beak)
                return False
            
            relation_clean = relation_response.strip().lower()
            
            # Enkel mapping av vanlige svar
            relation_map = {
                'venn': 'venn',
                'venninne': 'venn',
                'kollega': 'kollega',
                'gjest': 'gjest',
                'besøkende': 'gjest',
                'familie': 'familie',
                'søster': 'søster',
                'bror': 'bror',
                'mor': 'mor',
                'far': 'far'
            }
            
            relation = 'gjest'  # Default
            for key, value in relation_map.items():
                if key in relation_clean:
                    relation = value
                    break
            
            # Opprett ny bruker
            username = name_clean.lower().replace(' ', '_')
            user_manager.switch_user(
                username=username,
                display_name=name_clean,
                relation=relation
            )
            
            speak(f"Velkommen {name_clean}! Hyggelig å møte deg. Hva kan jeg hjelpe deg med?", speech_config, beak)
            print(f"✅ Opprettet og byttet til ny bruker: {name_clean} ({relation})", flush=True)
            return True
            
    except Exception as e:
        print(f"⚠️ Feil under brukerbytte: {e}", flush=True)
        speak("Beklager, det oppstod en feil. Jeg fortsetter som Osmund.", speech_config, beak)
        return False


def is_conversation_ending(user_text: str) -> bool:
    """
    Detekter om bruker vil avslutte samtalen basert på fraser.
    
    Args:
        user_text: Brukerens tekst
    
    Returns:
        True hvis samtalen skal avsluttes
    """
    user_lower = user_text.lower()
    
    # Avslutningsfraser
    ending_phrases = [
        "stopp",
        "slutt",
        "avslutt",
        "ha det",
        "farvel",
        "takk for hjelpen",
        "takk for meg",
        "det var alt",
        "det var det",
        "ferdig"
    ]
    
    return any(phrase in user_lower for phrase in ending_phrases)
