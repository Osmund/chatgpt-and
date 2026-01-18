#!/usr/bin/env python3
"""
Personality Analyzer - Adaptiv læring av Andas personlighet

Kjører nattlig analyse av samtaler og oppdaterer personlighetsprofil.
Kan bruke forskjellige AI-modeller: GPT-4o, Claude 3.5, Gemini 2.0 Flash
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import os
from dotenv import load_dotenv

# AI clients
from openai import OpenAI
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

load_dotenv()


@dataclass
class PersonalityProfile:
    """Andas personlighetsprofil basert på samtaler"""
    
    # Personlighetstrekk (0-10 skala)
    humor_level: float = 5.0          # Hvor mye humor bruker liker
    verbosity_level: float = 5.0       # Korte (0) vs lange (10) svar
    formality_level: float = 3.0       # Uformell (0) vs formell (10)
    enthusiasm_level: float = 5.0      # Rolig (0) vs entusiastisk (10)
    technical_depth: float = 5.0       # Enkel (0) vs dyp teknisk (10)
    
    # Atferd
    ask_followup_questions: bool = True
    use_emojis: bool = True
    proactive_suggestions: bool = True
    
    # Preferanser fra samtaler
    preferred_topics: List[str] = None
    engagement_patterns: Dict = None
    response_patterns: Dict = None
    
    # Metadata
    last_analyzed: str = None
    conversations_analyzed: int = 0
    confidence_score: float = 0.5  # Hvor sikker er vi på profilen
    
    def __post_init__(self):
        if self.preferred_topics is None:
            self.preferred_topics = []
        if self.engagement_patterns is None:
            self.engagement_patterns = {}
        if self.response_patterns is None:
            self.response_patterns = {}
        if self.last_analyzed is None:
            self.last_analyzed = datetime.now().isoformat()


class PersonalityAnalyzer:
    """Analyserer samtaler og oppdaterer personlighetsprofil"""
    
    def __init__(self, db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db"):
        self.db_path = db_path
        self._init_personality_table()
        
        # AI clients
        self.openai_client = OpenAI()
        
        if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            self.anthropic_client = None
        
        if GEMINI_AVAILABLE and os.getenv("GOOGLE_API_KEY"):
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            # Bruk gemini-1.5-flash for free tier kompatibilitet
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.gemini_model = None
    
    def _init_personality_table(self):
        """Opprett personality_profile tabell"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS personality_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                humor_level REAL DEFAULT 5.0,
                verbosity_level REAL DEFAULT 5.0,
                formality_level REAL DEFAULT 3.0,
                enthusiasm_level REAL DEFAULT 5.0,
                technical_depth REAL DEFAULT 5.0,
                ask_followup_questions INTEGER DEFAULT 1,
                use_emojis INTEGER DEFAULT 1,
                proactive_suggestions INTEGER DEFAULT 1,
                preferred_topics TEXT,
                engagement_patterns TEXT,
                response_patterns TEXT,
                last_analyzed TEXT,
                conversations_analyzed INTEGER DEFAULT 0,
                confidence_score REAL DEFAULT 0.5
            )
        """)
        
        # Sett inn default hvis tom
        c.execute("SELECT COUNT(*) FROM personality_profile")
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO personality_profile (id, last_analyzed) 
                VALUES (1, ?)
            """, (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()
    
    def get_recent_conversations(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """Hent nylige samtaler for analyse"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute("""
            SELECT user_text, ai_response, timestamp, user_name
            FROM messages 
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, limit))
        
        conversations = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return conversations
    
    def analyze_with_gpt4o(self, conversations: List[Dict]) -> PersonalityProfile:
        """Analyser med GPT-4o"""
        
        # Bygg prompt med samtalehistorikk
        conv_text = "\n\n".join([
            f"Bruker: {c['user_text']}\nAnda: {c['ai_response']}"
            for c in conversations[:50]  # Begrens til 50 for token limits
        ])
        
        analysis_prompt = f"""Du er en ekspert på personlighetsanalyse og brukeratferd.

Analyser følgende {len(conversations)} samtaler mellom Osmund og AI-assistenten Anda (en smart and med robotstemme).

SAMTALER:
{conv_text}

Analyser Osmunds preferanser og generer en personlighetsprofil for hvordan Anda bør oppføre seg:

1. **Humor level (0-10)**: Hvor mye liker Osmund humor og spøker?
2. **Verbosity level (0-10)**: Foretrekker Osmund korte (0) eller utdypende (10) svar?
3. **Formality level (0-10)**: Uformell (0) eller formell (10) tone?
4. **Enthusiasm level (0-10)**: Rolig (0) eller entusiastisk (10)?
5. **Technical depth (0-10)**: Enkel forklaring (0) eller dyp teknisk (10)?
6. **Ask followup**: Liker Osmund at Anda stiller oppfølgingsspørsmål?
7. **Use emojis**: Liker Osmund emojis i svar?
8. **Proactive suggestions**: Vil Osmund at Anda kommer med forslag?

VIKTIG: 
- Se på lengden av Osmunds svar (lang = engasjert)
- Se på oppfølgingsspørsmål (flere spørsmål = interessert)
- Se på tone i Osmunds språk
- Identifiser hvilke emner han engasjerer seg mest i

Svar med JSON:
{{
    "humor_level": 7.5,
    "verbosity_level": 6.0,
    "formality_level": 2.0,
    "enthusiasm_level": 6.5,
    "technical_depth": 8.0,
    "ask_followup_questions": true,
    "use_emojis": true,
    "proactive_suggestions": true,
    "preferred_topics": ["teknologi", "home automation", "programmering"],
    "engagement_patterns": {{
        "best_time": "kveld",
        "avg_conversation_length": 8,
        "response_speed_indicator": "rask på interessante emner"
    }},
    "response_patterns": {{
        "likes_detailed_explanations": true,
        "appreciates_concrete_examples": true,
        "prefers_norwegian": true
    }},
    "reasoning": "Kort forklaring av analysen",
    "confidence_score": 0.85
}}"""

        # Prøv først o1 (reasoning model, best for analyse)
        try:
            response = self.openai_client.chat.completions.create(
                model="o1",
                messages=[
                    {"role": "user", "content": f"Du er ekspert på personlighetsanalyse. Svar kun med valid JSON.\n\n{analysis_prompt}"}
                ]
            )
            print("✅ Bruker o1 (reasoning model)")
        except Exception as e:
            # Fallback til gpt-4o hvis o1 ikke tilgjengelig
            print(f"⚠️ o1 ikke tilgjengelig ({e}), bruker gpt-4o")
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Du er ekspert på personlighetsanalyse. Svar kun med valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
        
        analysis = json.loads(response.choices[0].message.content)
        
        # Konverter til PersonalityProfile
        profile = PersonalityProfile(
            humor_level=analysis.get("humor_level", 5.0),
            verbosity_level=analysis.get("verbosity_level", 5.0),
            formality_level=analysis.get("formality_level", 3.0),
            enthusiasm_level=analysis.get("enthusiasm_level", 5.0),
            technical_depth=analysis.get("technical_depth", 5.0),
            ask_followup_questions=analysis.get("ask_followup_questions", True),
            use_emojis=analysis.get("use_emojis", True),
            proactive_suggestions=analysis.get("proactive_suggestions", True),
            preferred_topics=analysis.get("preferred_topics", []),
            engagement_patterns=analysis.get("engagement_patterns", {}),
            response_patterns=analysis.get("response_patterns", {}),
            last_analyzed=datetime.now().isoformat(),
            conversations_analyzed=len(conversations),
            confidence_score=analysis.get("confidence_score", 0.7)
        )
        
        print(f"📊 GPT-4o Analyse:")
        print(f"   Reasoning: {analysis.get('reasoning', 'N/A')}")
        
        return profile
    
    def analyze_with_gemini(self, conversations: List[Dict]) -> PersonalityProfile:
        """Analyser med Gemini 2.0 Flash (GRATIS!)"""
        
        if not self.gemini_model:
            raise ValueError("Gemini API key ikke konfigurert")
        
        conv_text = "\n\n".join([
            f"Bruker: {c['user_text']}\nAnda: {c['ai_response']}"
            for c in conversations[:50]
        ])
        
        analysis_prompt = f"""Du er en ekspert på personlighetsanalyse og brukeratferd.

Analyser følgende {len(conversations)} samtaler mellom Osmund og AI-assistenten Anda (en smart and med robotstemme).

SAMTALER:
{conv_text}

Analyser Osmunds preferanser og generer en personlighetsprofil for hvordan Anda bør oppføre seg.

Svar med JSON format med disse feltene:
- humor_level (0-10): Hvor mye liker Osmund humor?
- verbosity_level (0-10): Korte (0) eller lange (10) svar?
- formality_level (0-10): Uformell (0) eller formell (10)?
- enthusiasm_level (0-10): Rolig (0) eller entusiastisk (10)?
- technical_depth (0-10): Enkel (0) eller teknisk dyp (10)?
- ask_followup_questions (boolean)
- use_emojis (boolean)
- proactive_suggestions (boolean)
- preferred_topics (array)
- engagement_patterns (object)
- response_patterns (object)
- reasoning (string)
- confidence_score (0-1)"""

        response = self.gemini_model.generate_content(analysis_prompt)
        
        # Parse JSON fra respons
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        analysis = json.loads(text.strip())
        
        profile = PersonalityProfile(
            humor_level=analysis.get("humor_level", 5.0),
            verbosity_level=analysis.get("verbosity_level", 5.0),
            formality_level=analysis.get("formality_level", 3.0),
            enthusiasm_level=analysis.get("enthusiasm_level", 5.0),
            technical_depth=analysis.get("technical_depth", 5.0),
            ask_followup_questions=analysis.get("ask_followup_questions", True),
            use_emojis=analysis.get("use_emojis", True),
            proactive_suggestions=analysis.get("proactive_suggestions", True),
            preferred_topics=analysis.get("preferred_topics", []),
            engagement_patterns=analysis.get("engagement_patterns", {}),
            response_patterns=analysis.get("response_patterns", {}),
            last_analyzed=datetime.now().isoformat(),
            conversations_analyzed=len(conversations),
            confidence_score=analysis.get("confidence_score", 0.7)
        )
        
        print(f"📊 Gemini 2.0 Flash Analyse:")
        print(f"   Reasoning: {analysis.get('reasoning', 'N/A')}")
        
        return profile
    
    def save_profile(self, profile: PersonalityProfile):
        """Lagre personlighetsprofil til database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE personality_profile SET
                humor_level = ?,
                verbosity_level = ?,
                formality_level = ?,
                enthusiasm_level = ?,
                technical_depth = ?,
                ask_followup_questions = ?,
                use_emojis = ?,
                proactive_suggestions = ?,
                preferred_topics = ?,
                engagement_patterns = ?,
                response_patterns = ?,
                last_analyzed = ?,
                conversations_analyzed = ?,
                confidence_score = ?
            WHERE id = 1
        """, (
            profile.humor_level,
            profile.verbosity_level,
            profile.formality_level,
            profile.enthusiasm_level,
            profile.technical_depth,
            1 if profile.ask_followup_questions else 0,
            1 if profile.use_emojis else 0,
            1 if profile.proactive_suggestions else 0,
            json.dumps(profile.preferred_topics),
            json.dumps(profile.engagement_patterns),
            json.dumps(profile.response_patterns),
            profile.last_analyzed,
            profile.conversations_analyzed,
            profile.confidence_score
        ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Personlighetsprofil lagret!")
    
    def load_profile(self) -> PersonalityProfile:
        """Last personlighetsprofil fra database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM personality_profile WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        if not row:
            return PersonalityProfile()
        
        return PersonalityProfile(
            humor_level=row['humor_level'],
            verbosity_level=row['verbosity_level'],
            formality_level=row['formality_level'],
            enthusiasm_level=row['enthusiasm_level'],
            technical_depth=row['technical_depth'],
            ask_followup_questions=bool(row['ask_followup_questions']),
            use_emojis=bool(row['use_emojis']),
            proactive_suggestions=bool(row['proactive_suggestions']),
            preferred_topics=json.loads(row['preferred_topics']) if row['preferred_topics'] else [],
            engagement_patterns=json.loads(row['engagement_patterns']) if row['engagement_patterns'] else {},
            response_patterns=json.loads(row['response_patterns']) if row['response_patterns'] else {},
            last_analyzed=row['last_analyzed'],
            conversations_analyzed=row['conversations_analyzed'],
            confidence_score=row['confidence_score']
        )
    
    def run_analysis(self, model: str = "gemini", days: int = 7):
        """
        Kjør full personlighetsanalyse
        
        Args:
            model: "gemini" (gratis), "gpt4o" ($), eller "claude" ($$$)
            days: Hvor mange dager tilbake å analysere
        """
        print(f"🔍 Starter personlighetsanalyse med {model}...")
        print(f"📅 Analyserer samtaler fra siste {days} dager...")
        
        # Hent samtaler
        conversations = self.get_recent_conversations(days=days)
        
        if not conversations:
            print("❌ Ingen samtaler funnet!")
            return
        
        print(f"💬 Fant {len(conversations)} samtaler")
        
        # Analyser med valgt modell
        if model == "gemini":
            profile = self.analyze_with_gemini(conversations)
        elif model == "gpt4o":
            profile = self.analyze_with_gpt4o(conversations)
        elif model == "claude":
            # TODO: Implementer Claude hvis ønsket
            raise NotImplementedError("Claude ikke implementert ennå")
        else:
            raise ValueError(f"Ukjent modell: {model}")
        
        # Lagre profil
        self.save_profile(profile)
        
        # Print resultat
        print("\n" + "="*60)
        print("🎭 ANDAS PERSONLIGHETSPROFIL")
        print("="*60)
        print(f"💬 Humor level:        {profile.humor_level:.1f}/10")
        print(f"📝 Verbosity:          {profile.verbosity_level:.1f}/10")
        print(f"👔 Formality:          {profile.formality_level:.1f}/10")
        print(f"🎉 Enthusiasm:         {profile.enthusiasm_level:.1f}/10")
        print(f"🔧 Technical depth:    {profile.technical_depth:.1f}/10")
        print(f"❓ Followup questions: {'Ja' if profile.ask_followup_questions else 'Nei'}")
        print(f"😊 Use emojis:         {'Ja' if profile.use_emojis else 'Nei'}")
        print(f"💡 Proactive:          {'Ja' if profile.proactive_suggestions else 'Nei'}")
        print(f"\n📚 Preferred topics:   {', '.join(profile.preferred_topics[:5])}")
        print(f"🎯 Confidence score:   {profile.confidence_score:.0%}")
        print(f"📊 Analyzed convos:    {profile.conversations_analyzed}")
        print("="*60)


def main():
    """CLI for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyser Andas personlighet")
    parser.add_argument("--model", choices=["gemini", "gpt4o", "claude"], 
                       default="gemini", help="AI model å bruke")
    parser.add_argument("--days", type=int, default=7, 
                       help="Dager tilbake å analysere")
    parser.add_argument("--show", action="store_true",
                       help="Vis nåværende profil")
    
    args = parser.parse_args()
    
    analyzer = PersonalityAnalyzer()
    
    if args.show:
        profile = analyzer.load_profile()
        print(f"\n🎭 Nåværende personlighetsprofil:")
        print(f"   Humor: {profile.humor_level:.1f}/10")
        print(f"   Verbosity: {profile.verbosity_level:.1f}/10")
        print(f"   Technical: {profile.technical_depth:.1f}/10")
        print(f"   Topics: {', '.join(profile.preferred_topics[:3])}")
        print(f"   Last analyzed: {profile.last_analyzed}")
    else:
        analyzer.run_analysis(model=args.model, days=args.days)


if __name__ == "__main__":
    main()
