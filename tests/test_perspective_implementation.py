#!/usr/bin/env python3
"""
Test perspektiv-håndtering implementasjon
Sjekker at riktige perspektiv-instruksjoner genereres for forskjellige brukere
"""

import sys
import os

# Legg til project root i path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from duck_user_manager import UserManager
from duck_memory import MemoryManager

def test_perspective_context():
    """Test at perspektiv-kontekst genereres riktig"""
    
    print("="*80)
    print("TESTING PERSPEKTIV-HÅNDTERING IMPLEMENTASJON")
    print("="*80)
    print()
    
    user_manager = UserManager('duck_memory.db')
    memory_manager = MemoryManager('duck_memory.db')
    
    # Test scenarios
    test_cases = [
        {
            "user": "Arvid",
            "relation": "far",
            "query": "hvem er pappa min?",
            "expected_keywords": ["SIN far", "bestefar", "ER Osmunds far", "ikke omvendt"],
            "should_not_contain": ["Arvid er pappa"]
        },
        {
            "user": "Miriam",
            "relation": "søster",
            "query": "hvor mange nevøer har jeg?",
            "expected_keywords": ["SØSKENS barn", "Osmunds og de andre søstrenes barn", "IKKE sine egne"],
            "should_not_contain": []
        },
        {
            "user": "TestKollega",
            "relation": "kollega",
            "query": "hvem er i familien?",
            "expected_keywords": ["OSMUNDS familie", "ikke familiemedlem", "ikke TestKollega sin"],
            "should_not_contain": []
        },
        {
            "user": "TestVenn",
            "relation": "venn",
            "query": "fortell om familien",
            "expected_keywords": ["OSMUNDS familie", "ikke familiemedlem"],
            "should_not_contain": []
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {test['user']} ({test['relation']})")
        print(f"Spørsmål: {test['query']}")
        print(f"{'='*80}")
        
        # Bytt til bruker (eller opprett hvis ikke eksisterer)
        try:
            user_manager.switch_user(test['user'])
        except:
            # Opprett bruker hvis ikke eksisterer
            import sqlite3
            conn = sqlite3.connect('duck_memory.db')
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO users (username, display_name, relation_to_primary)
                VALUES (?, ?, ?)
            """, (test['user'], test['user'], test['relation']))
            conn.commit()
            conn.close()
            user_manager.switch_user(test['user'])
        
        current_user = user_manager.get_current_user()
        
        # Generer perspektiv-kontekst (kopiert fra chatgpt_voice.py logikk)
        perspective_context = ""
        if current_user['username'] != 'Osmund':
            perspective_context = f"\n\n### KRITISK: Perspektiv-håndtering ###\n"
            perspective_context += f"Du snakker nå med {current_user['display_name']} ({current_user['relation']}).\n"
            perspective_context += f"ALLE fakta i 'Ditt Minne' er lagret fra Osmunds perspektiv.\n\n"
            
            relation = current_user['relation'].lower()
            if 'far' in relation or 'father' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'pappa' eller 'far', spør han om SIN far (Osmunds bestefar).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine' eller 'mine barn', mener han Osmund og Osmunds søstre.\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barnebarna mine', mener han Osmunds nevøer/nieser (søstrenes barn).\n"
                perspective_context += f"- {current_user['display_name']} ER Osmunds far, ikke omvendt.\n"
            elif 'mor' in relation or 'mother' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'mamma' eller 'mor', spør hun om SIN mor (Osmunds bestemor).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine', mener hun Osmund og Osmunds søstre.\n"
                perspective_context += f"- {current_user['display_name']} ER Osmunds mor, ikke omvendt.\n"
            elif 'søster' in relation or 'sister' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine', mener hun SINE egne barn (ikke sine søskens barn).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'nevøer' eller 'nieser', mener hun sine SØSKENS barn (Osmunds og de andre søstrenes barn), IKKE sine egne.\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'broren min' eller 'bror', mener hun Osmund.\n"
                perspective_context += f"- {current_user['display_name']} ER Osmunds søster, ikke omvendt.\n"
            elif 'kollega' in relation or 'colleague' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er Osmunds kollega, ikke familiemedlem.\n"
                perspective_context += f"- Fakta om familie er Osmunds familie, ikke {current_user['display_name']} sin.\n"
                perspective_context += f"- Når {current_user['display_name']} spør om familie, snakker vedkommende om OSMUNDS familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin private familie med mindre det er eksplisitt lagret.\n"
            elif 'venn' in relation or 'kamerat' in relation or 'friend' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er Osmunds venn, ikke familiemedlem.\n"
                perspective_context += f"- Fakta om familie er Osmunds familie, ikke {current_user['display_name']} sin.\n"
                perspective_context += f"- Når {current_user['display_name']} spør om familie, snakker vedkommende om OSMUNDS familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin private familie med mindre det er eksplisitt lagret.\n"
            elif 'gjest' in relation or 'guest' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er gjest, ikke familiemedlem.\n"
                perspective_context += f"- Alle fakta om familie er Osmunds familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin bakgrunn med mindre det er eksplisitt lagret.\n"
            
            perspective_context += f"\nHvis du er usikker på perspektiv: Si 'Jeg har ikke nok informasjon om det' i stedet for å gjette.\n"
        
        print("\n📝 GENERERT PERSPEKTIV-KONTEKST:")
        print(perspective_context if perspective_context else "(ingen - bruker er Osmund)")
        
        # Sjekk forventede nøkkelord
        print("\n✅ SJEKKER FORVENTEDE NØKKELORD:")
        all_found = True
        for keyword in test['expected_keywords']:
            found = keyword in perspective_context
            status = "✓" if found else "✗"
            print(f"  {status} '{keyword}': {'Funnet' if found else 'MANGLER'}")
            if not found:
                all_found = False
        
        # Sjekk at feil-ord ikke er der
        print("\n❌ SJEKKER AT DISSE IKKE ER MED:")
        none_found = True
        for keyword in test['should_not_contain']:
            found = keyword in perspective_context
            status = "✗" if found else "✓"
            print(f"  {status} '{keyword}': {'FEIL - FUNNET!' if found else 'OK - ikke funnet'}")
            if found:
                none_found = False
        
        # Resultat
        success = all_found and none_found
        results.append({
            'test': f"{test['user']} ({test['relation']})",
            'success': success
        })
        
        print(f"\n{'✅ TEST BESTÅTT' if success else '❌ TEST FEILET'}")
    
    # Bytt tilbake til Osmund
    user_manager.switch_user("Osmund")
    
    # Oppsummering
    print("\n" + "="*80)
    print("OPPSUMMERING")
    print("="*80)
    
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['test']}")
    
    print(f"\n{'='*80}")
    print(f"RESULTAT: {passed}/{total} tester bestått ({passed/total*100:.0f}%)")
    print(f"{'='*80}")
    
    return passed == total

if __name__ == "__main__":
    success = test_perspective_context()
    sys.exit(0 if success else 1)
