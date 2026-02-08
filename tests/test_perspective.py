#!/usr/bin/env python3
"""
Test perspektiv-håndtering for ulike brukere
"""

import openai
import os

# Test scenarios
scenarios = [
    {
        "user": "Arvid",
        "relation": "far (Osmunds far)",
        "question": "Kan du fortelle meg om pappa?",
        "expected": "Jeg har ikke informasjon om din far (Osmunds bestefar)",
    },
    {
        "user": "Arvid", 
        "relation": "far (Osmunds far)",
        "question": "Hvor mange barn har jeg?",
        "expected": "4 barn: Osmund, Miriam, Astrid og Gine",
    },
    {
        "user": "Miriam",
        "relation": "søster (Osmunds eldste søster)",
        "question": "Hvem er mine nevøer og nieser?",
        "expected": "Astrids barn (Mila, Luna) og Gines barn (Markus, Mathilde)",
    },
    {
        "user": "Arvid",
        "relation": "far (Osmunds far)", 
        "question": "Hva heter barnebarna mine?",
        "expected": "Sivert, Elise, Mila, Luna, Markus, Mathilde",
    },
]

# Sample facts (fra database)
sample_facts = """
- father_name: Arvid
- father_birthday: 21-11
- father_birthplace: Sokndal
- father_location: Sokndal
- sister_1_name: Miriam
- sister_1_birthday: 31-01
- sister_1_husband_name: Morten
- sister_1_child_1_name: Sivert
- sister_1_child_2_name: Elise
- sister_2_name: Astrid
- sister_2_birthday: 16-02
- sister_2_husband_name: Tony
- sister_2_child_1_name: Mila
- sister_2_child_2_name: Luna
- sister_3_name: Gine
- sister_3_birthday: 15-01
- sister_3_husband_name: Sven
- sister_3_child_1_name: Markus
- sister_3_child_2_name: Mathilde
"""

def build_test_prompt(user, relation, question):
    """Bygg prompt som systemet ville sendt til AI"""
    
    perspective_context = f"""
## VIKTIG: PERSPEKTIV-KONTEKST ##

Du snakker nå med: {user}
Relasjon til Osmund: {relation}

ALLE facts nedenfor er lagret fra OSMUNDS perspektiv. Du må tolke dem basert på hvem du snakker med:

EKSEMPLER PÅ TOLKNING:
- "father_name: Arvid" = Osmunds far
  → Hvis DU snakker med Arvid: Dette er DEG selv
  → Hvis Arvid spør om "pappa": Han spør om SIN far (ikke Osmund)
  
- "sister_1_name: Miriam" = Osmunds søster  
  → Hvis DU snakker med Arvid: Dette er Arvids DATTER
  → Hvis DU snakker med Miriam: Dette er DEG selv
  
- "sister_1_child_1_name: Sivert" = Osmunds nevø (Miriams sønn)
  → Hvis DU snakker med Arvid: Dette er Arvids BARNEBARN
  → Hvis DU snakker med Miriam: Dette er Miriams BARN/SØNN

TOMMELFINGERREGEL:
1. Hvis personen spør om "pappa/far" - søk DERES forelder (ikke nødvendigvis i facts)
2. Hvis personen spør om "mine barn" - finn alle som er deres barn i forhold til Osmund
3. Hvis personen spør om "barnebarn" - finn alle som er deres barnebarn via familietreet
"""

    prompt = f"""{perspective_context}

### Fakta om brukeren (fra Osmunds perspektiv) ###
{sample_facts}

### Brukerens spørsmål ###
{question}
"""
    
    return prompt

def test_scenario(scenario, api_key):
    """Test ett scenario"""
    print(f"\n{'='*70}")
    print(f"TEST: {scenario['user']} spør: \"{scenario['question']}\"")
    print(f"Forventet: {scenario['expected']}")
    print(f"{'='*70}\n")
    
    prompt = build_test_prompt(scenario['user'], scenario['relation'], scenario['question'])
    
    print("PROMPT SOM SENDES TIL AI:")
    print("-" * 70)
    print(prompt)
    print("-" * 70)
    
    # Test med OpenAI
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Du er Anda, en hjelpsom norsk AI-assistent. Svar kort og presist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        ai_response = response.choices[0].message.content
        
        print("\nAI SVAR:")
        print("-" * 70)
        print(ai_response)
        print("-" * 70)
        
        return ai_response
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        return None

if __name__ == "__main__":
    # Hent API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        # Prøv å lese fra .env fil
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('OPENAI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        break
        except:
            pass
    
    if not api_key:
        print("❌ Fant ikke OPENAI_API_KEY")
        print("Sett den med: export OPENAI_API_KEY=sk-...")
        exit(1)
    
    print("🧪 TESTER PERSPEKTIV-HÅNDTERING MED GPT-4\n")
    
    # Kjør alle tester
    results = []
    for scenario in scenarios:
        response = test_scenario(scenario, api_key)
        results.append({
            'scenario': scenario,
            'response': response
        })
        
        # Vent litt mellom requests
        import time
        time.sleep(1)
    
    # Oppsummering
    print("\n" + "="*70)
    print("OPPSUMMERING")
    print("="*70)
    
    for i, result in enumerate(results, 1):
        scenario = result['scenario']
        print(f"\n{i}. {scenario['user']}: \"{scenario['question']}\"")
        print(f"   Forventet: {scenario['expected']}")
        if result['response']:
            print(f"   AI svarte: {result['response'][:100]}...")
        else:
            print(f"   ❌ Ingen respons")
