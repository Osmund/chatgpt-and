#!/usr/bin/env python3
"""
Adaptive Greetings - Tilpasser Andas hilsener basert på personlighet
"""

import random
from datetime import datetime
from src.duck_database import get_db


def get_adaptive_greeting(db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db", user_name: str = "på du") -> str:
    """
    Generer adaptiv hilsen basert på personlighetsprofil og tid på døgnet.
    
    Args:
        db_path: Path til duck_memory.db
        user_name: Navn på bruker
    
    Returns:
        Personalisert hilsen-string
    """
    try:
        conn = get_db().connection()
        c = conn.cursor()
        
        c.execute("SELECT * FROM personality_profile WHERE id = 1")
        profile = c.fetchone()
        
        if not profile:
            # Fallback til default hilsen
            return f"Hei {user_name}, hva kan jeg hjelpe deg med?"
        
        # Konverter sqlite3.Row til dict for å kunne bruke dictionary access
        profile = dict(profile)
        
        humor = profile['humor_level']
        enthusiasm = profile['enthusiasm_level']
        formality = profile['formality_level']
        use_emojis = bool(profile['use_emojis'])
        
        # Tid på døgnet
        hour = datetime.now().hour
        
        # Bygg hilsen basert på personlighet
        greetings = []
        
        # FORMALITY nivå
        if formality <= 3:
            # Uformell
            base_greetings = [
                f"Hæ {user_name}",
                f"Heisann {user_name}",
                f"Halla {user_name}",
                f"Hei {user_name}",
                f"Yo {user_name}"
            ]
        elif formality <= 6:
            # Moderat
            base_greetings = [
                f"Hei {user_name}",
                f"Hallo {user_name}",
                f"God dag {user_name}"
            ]
        else:
            # Formell
            base_greetings = [
                f"Goddag {user_name}",
                f"Velkommen {user_name}",
                f"Hei {user_name}"
            ]
        
        greeting = random.choice(base_greetings)
        
        # ENTHUSIASM nivå
        if enthusiasm >= 7:
            # Høy entusiasme
            if hour < 10:
                greeting += "! God morgen!"
            elif hour < 18:
                greeting += "! Så fint å høre fra deg!"
            else:
                greeting += "! Så hyggelig!"
        elif enthusiasm >= 5:
            # Moderat
            greeting += "!"
        else:
            # Lav
            greeting += "."
        
        # HUMOR nivå
        if humor >= 7:
            # Mye humor
            humor_additions = [
                " Klar for andeprat?",
                " Hva kan denne anden hjelpe med i dag?",
                " Kvakk kvakk! Hva skjer?",
                " Jeg er klar! Er du?",
                " La oss dykke ned i det!"
            ]
            greeting += random.choice(humor_additions)
        elif humor >= 5:
            # Litt humor
            humor_additions = [
                " Hva kan jeg hjelpe med?",
                " Hva skal vi ta tak i?",
                " Hva trenger du hjelp til?"
            ]
            greeting += random.choice(humor_additions)
        else:
            # Minimal humor
            greeting += " Hva kan jeg hjelpe deg med?"
        
        return greeting
        
    except Exception as e:
        print(f"⚠️ Kunne ikke generere adaptiv hilsen: {e}")
        return f"Hei {user_name}, hva kan jeg hjelpe deg med?"


def get_adaptive_goodbye(db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db") -> str:
    """
    Generer adaptiv avslutningshilsen basert på personlighetsprofil.
    
    Returns:
        Personalisert avslutning
    """
    try:
        conn = get_db().connection()
        c = conn.cursor()
        
        c.execute("SELECT * FROM personality_profile WHERE id = 1")
        profile = c.fetchone()
        
        if not profile:
            return "Greit! Ha det bra!"
        
        # Konverter sqlite3.Row til dict for å kunne bruke dictionary access
        profile = dict(profile)
        
        humor = profile['humor_level']
        enthusiasm = profile['enthusiasm_level']
        formality = profile['formality_level']
        
        goodbyes = []
        
        # Bygg avslutninger basert på personlighet
        if formality <= 3:
            # Uformell
            if enthusiasm >= 7:
                # Høy entusiasme + uformell
                goodbyes = [
                    "Topp! Vi snakkes!",
                    "Perfekt! Ha en strålende dag!",
                    "Supert! Vi høres!",
                    "Knall! Ta det fint!",
                    "Greit! Hadde vært hyggelig!"
                ]
            elif enthusiasm >= 5:
                # Moderat
                goodbyes = [
                    "Greit! Ha det bra!",
                    "Ok! Vi snakkes!",
                    "Fint! Ha en fin dag!",
                    "Greit! Ta det fint!"
                ]
            else:
                # Lav entusiasme
                goodbyes = [
                    "Ok, ha det.",
                    "Greit, vi snakkes.",
                    "Ok."
                ]
        elif formality <= 6:
            # Moderat formell
            goodbyes = [
                "Fint! Ha en fin dag!",
                "Greit! Vi snakkes senere!",
                "Ok! Ha det bra!",
                "Perfekt! Ta det fint!"
            ]
        else:
            # Formell
            goodbyes = [
                "Veldig bra. Ha en fortsatt god dag.",
                "Utmerket. Vi snakkes.",
                "Fint. Ha det godt."
            ]
        
        # HUMOR tillegg
        if humor >= 7:
            humor_additions = [
                " Kvakk for nå!",
                " Anda out!",
                " Til neste andeprat!",
                " Kvakk kvakk!"
            ]
            return random.choice(goodbyes) + random.choice(humor_additions)
        else:
            return random.choice(goodbyes)
        
    except Exception as e:
        print(f"⚠️ Kunne ikke generere adaptiv avslutning: {e}")
        return "Greit! Ha det bra!"


if __name__ == "__main__":
    # Test
    print("🎭 Testing adaptive greetings:")
    print(f"Greeting: {get_adaptive_greeting(user_name='Osmund')}")
    print(f"Goodbye: {get_adaptive_goodbye()}")
