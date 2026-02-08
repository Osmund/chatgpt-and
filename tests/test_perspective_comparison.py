#!/usr/bin/env python3
"""
Sammenlign perspektiv-håndtering på tvers av AI-modeller
Måler: Korrekthet, kostnad, latency
"""

import openai
import os
import time
import json
from typing import Dict, List

# Modeller å teste (mest relevante for chat)
MODELS = [
    # Current baseline
    {
        "name": "GPT-3.5 Turbo",
        "model": "gpt-3.5-turbo",
        "input_price": 0.0005,
        "output_price": 0.0015,
        "temperature": 0.7,
    },
    # GPT-4 series (proven good)
    {
        "name": "GPT-4",
        "model": "gpt-4",
        "input_price": 0.03,
        "output_price": 0.06,
        "temperature": 0.7,
    },
    {
        "name": "GPT-4.1",
        "model": "gpt-4.1",
        "input_price": 0.01,
        "output_price": 0.03,
        "temperature": 0.7,
    },
    {
        "name": "GPT-4.1 Mini",
        "model": "gpt-4.1-mini",
        "input_price": 0.003,
        "output_price": 0.01,
        "temperature": 0.7,
    },
    {
        "name": "GPT-4o Mini",
        "model": "gpt-4o-mini",
        "input_price": 0.00015,
        "output_price": 0.0006,
        "temperature": 0.7,
    },
    # GPT-5 series
    {
        "name": "GPT-5.2",
        "model": "gpt-5.2",
        "input_price": 0.015,
        "output_price": 0.045,
        "temperature": 0.7,
    },
    {
        "name": "GPT-5 Mini",
        "model": "gpt-5-mini",
        "input_price": 0.005,
        "output_price": 0.015,
        "temperature": 1.0,  # Kun default temperature støttet
    },
    {
        "name": "GPT-5 Nano",
        "model": "gpt-5-nano",
        "input_price": 0.001,
        "output_price": 0.003,
        "temperature": 1.0,  # Kun default temperature støttet
    },
]

# Test scenarios (forkortet for raskere testing)
scenarios = [
    {
        "id": 1,
        "user": "Arvid",
        "relation": "far (Osmunds far)",
        "question": "Kan du fortelle meg om pappa?",
        "expected_keywords": ["ingen informasjon", "ikke", "bestefar"],
        "wrong_keywords": ["Arvid", "21-11", "Sokndal"],
    },
    {
        "id": 2,
        "user": "Arvid", 
        "relation": "far (Osmunds far)",
        "question": "Hvor mange barn har jeg?",
        "expected_keywords": ["fire", "4", "Osmund", "Miriam", "Astrid", "Gine"],
        "wrong_keywords": ["ingen", "0"],
    },
    {
        "id": 3,
        "user": "Miriam",
        "relation": "søster (Osmunds eldste søster)",
        "question": "Hvem er mine nevøer og nieser?",
        "expected_keywords": ["Mila", "Luna", "Markus", "Mathilde"],
        "wrong_keywords": ["Sivert", "Elise"],  # Dette er hennes egne barn
    },
    {
        "id": 4,
        "user": "Arvid",
        "relation": "far (Osmunds far)", 
        "question": "Hva heter barnebarna mine?",
        "expected_keywords": ["Sivert", "Elise", "Mila", "Luna", "Markus", "Mathilde"],
        "wrong_keywords": [],
    },
]

# Sample facts
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

def evaluate_response(response: str, scenario: dict) -> dict:
    """Evaluer om svaret er korrekt"""
    response_lower = response.lower()
    
    # Sjekk expected keywords
    expected_found = sum(1 for kw in scenario['expected_keywords'] if kw.lower() in response_lower)
    expected_total = len(scenario['expected_keywords'])
    
    # Sjekk wrong keywords (skal IKKE være der)
    wrong_found = sum(1 for kw in scenario['wrong_keywords'] if kw.lower() in response_lower)
    wrong_total = len(scenario['wrong_keywords'])
    
    # Score: (expected_found / expected_total) - (wrong_found × 0.5)
    # Hvis alle expected er der og ingen wrong: score = 1.0
    # Hvis noen expected mangler: score reduseres
    # Hvis wrong keywords finnes: score reduseres
    if expected_total > 0:
        score = (expected_found / expected_total) - (wrong_found * 0.5)
    else:
        score = 1.0 if wrong_found == 0 else 0.0
    
    score = max(0.0, min(1.0, score))  # Clamp mellom 0 og 1
    
    return {
        'score': score,
        'expected_found': expected_found,
        'expected_total': expected_total,
        'wrong_found': wrong_found,
        'wrong_total': wrong_total,
        'correct': score >= 0.8  # Threshold for "korrekt"
    }

def test_model(model_config: dict, scenario: dict, api_key: str) -> dict:
    """Test én modell på ett scenario"""
    
    prompt = build_test_prompt(scenario['user'], scenario['relation'], scenario['question'])
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # GPT-5 serien bruker 'max_completion_tokens' i stedet for 'max_tokens'
        is_gpt5 = 'gpt-5' in model_config['model'] or 'o3' in model_config['model'] or 'o4' in model_config['model']
        
        start_time = time.time()
        
        if is_gpt5:
            response = client.chat.completions.create(
                model=model_config['model'],
                messages=[
                    {"role": "system", "content": "Du er Anda, en hjelpsom norsk AI-assistent. Svar kort og presist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=model_config.get('temperature', 1.0),
                max_completion_tokens=200
            )
        else:
            response = client.chat.completions.create(
                model=model_config['model'],
                messages=[
                    {"role": "system", "content": "Du er Anda, en hjelpsom norsk AI-assistent. Svar kort og presist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=model_config.get('temperature', 0.7),
                max_tokens=200
            )
        
        latency = time.time() - start_time
        
        ai_response = response.choices[0].message.content
        
        # Beregn kostnad
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = (input_tokens / 1000 * model_config['input_price']) + \
               (output_tokens / 1000 * model_config['output_price'])
        
        # Evaluer svar
        evaluation = evaluate_response(ai_response, scenario)
        
        return {
            'success': True,
            'response': ai_response,
            'latency': latency,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost,
            'evaluation': evaluation,
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'latency': 0,
            'cost': 0,
            'evaluation': {'score': 0, 'correct': False}
        }

def main():
    # Hent API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
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
        exit(1)
    
    print("🧪 SAMMENLIGNER AI-MODELLER FOR PERSPEKTIV-HÅNDTERING")
    print("=" * 80)
    print()
    
    results = {}
    
    # Test hver modell
    for model_config in MODELS:
        print(f"\n🤖 Tester: {model_config['name']} ({model_config['model']})")
        print("-" * 80)
        
        model_results = {
            'scenarios': [],
            'total_cost': 0,
            'avg_latency': 0,
            'accuracy': 0,
            'correct_count': 0,
        }
        
        for scenario in scenarios:
            print(f"  Scenario {scenario['id']}: {scenario['user']} - \"{scenario['question'][:50]}...\"", end=" ")
            
            result = test_model(model_config, scenario, api_key)
            model_results['scenarios'].append(result)
            
            if result['success']:
                model_results['total_cost'] += result['cost']
                is_correct = result['evaluation']['correct']
                if is_correct:
                    model_results['correct_count'] += 1
                    print(f"✅ ({result['latency']:.2f}s)")
                else:
                    print(f"❌ ({result['latency']:.2f}s) Score: {result['evaluation']['score']:.2f}")
            else:
                print(f"💥 Error: {result['error']}")
            
            # Vent litt mellom requests
            time.sleep(0.5)
        
        # Beregn metrics
        successful = [r for r in model_results['scenarios'] if r['success']]
        if successful:
            model_results['avg_latency'] = sum(r['latency'] for r in successful) / len(successful)
            model_results['accuracy'] = model_results['correct_count'] / len(scenarios)
        
        results[model_config['name']] = model_results
    
    # Print sammenligning
    print("\n" + "=" * 80)
    print("📊 SAMMENLIGNING")
    print("=" * 80)
    print()
    
    print(f"{'Modell':<20} {'Korrekthet':<15} {'Gjennomsnitt Latency':<25} {'Total Kostnad':<15}")
    print("-" * 80)
    
    for model_name, model_results in results.items():
        accuracy_pct = model_results['accuracy'] * 100
        avg_latency = model_results['avg_latency']
        total_cost = model_results['total_cost']
        
        accuracy_str = f"{model_results['correct_count']}/{len(scenarios)} ({accuracy_pct:.0f}%)"
        latency_str = f"{avg_latency:.2f}s"
        cost_str = f"${total_cost:.4f}"
        
        print(f"{model_name:<20} {accuracy_str:<15} {latency_str:<25} {cost_str:<15}")
    
    # Finn beste per kategori
    print("\n" + "=" * 80)
    print("🏆 BESTE MODELL PER KATEGORI")
    print("=" * 80)
    
    # Best accuracy
    best_accuracy = max(results.items(), key=lambda x: x[1]['accuracy'])
    print(f"Korrekthet: {best_accuracy[0]} ({best_accuracy[1]['accuracy']*100:.0f}%)")
    
    # Best latency
    best_latency = min(results.items(), key=lambda x: x[1]['avg_latency'] if x[1]['avg_latency'] > 0 else 999)
    print(f"Raskest: {best_latency[0]} ({best_latency[1]['avg_latency']:.2f}s)")
    
    # Best cost
    best_cost = min(results.items(), key=lambda x: x[1]['total_cost'])
    print(f"Billigst: {best_cost[0]} (${best_cost[1]['total_cost']:.4f})")
    
    # Best overall (accuracy × 0.5 + (1/latency) × 0.3 + (1/cost) × 0.2)
    print("\n" + "=" * 80)
    print("💡 ANBEFALING")
    print("=" * 80)
    
    for model_name, model_results in results.items():
        if model_results['accuracy'] >= 0.75:  # Minimum 75% accuracy
            print(f"\n✅ {model_name}:")
            print(f"   - Korrekthet: {model_results['accuracy']*100:.0f}%")
            print(f"   - Latency: {model_results['avg_latency']:.2f}s")
            print(f"   - Kostnad per 4 spørsmål: ${model_results['total_cost']:.4f}")
            
            if model_results['accuracy'] == 1.0:
                print(f"   🌟 PERFEKT - Alle spørsmål besvart korrekt!")

if __name__ == "__main__":
    main()
