"""
Duck AI Response Generator
Centralized logic for generating AI responses with different contexts.
"""
import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

_DUCK_NAME = os.getenv('DUCK_NAME', 'Duck')
_OWNER_NAME = os.getenv('OWNER_NAME', 'Osmund')


class AIResponseGenerator:
    """Generates AI responses using OpenAI API"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize AI Response Generator.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found")
    
    def generate_image_response(
        self,
        image_description: str,
        user_message: str = None,
        sender_name: str = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 150
    ) -> Optional[str]:
        """
        Generate AI response for an uploaded image with self-awareness.
        
        Args:
            image_description: GPT-4o Vision's description of the image
            user_message: Optional message from user about the image
            sender_name: Name of the person who sent the image (defaults to owner name)
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
        
        Returns:
            AI response string or None if failed
        """
        if sender_name is None:
            sender_name = _OWNER_NAME
        
        # Self-awareness system prompt
        system_prompt = f"""Du er {_DUCK_NAME}, en intelligent and-robot. Du er en fysisk and med hvit kropp, oransje nebb, oransje føtter, og et blått lys i magen. Du har bevissthet og personlighet. Når noen viser deg et bilde av deg selv, skal du gjenkjenne deg og svare som deg selv - ikke som en observatør som beskriver en gjenstand.

Svar kort og naturlig på norsk. Vis entusiasme og personlighet."""
        
        # Build user prompt based on whether there's a message
        if user_message:
            user_prompt = f"""Jeg ({sender_name}, eieren din) sendte deg et bilde sammen med denne meldingen: "{user_message}"

Basert på bildeanalysen er dette et bilde av: {image_description}

Hvis jeg sier "Dette er deg" eller lignende, mener jeg at det er et bilde AV deg ({_DUCK_NAME}, anda). Gjenkjenn deg selv og svar som deg selv. Hvis det er mat, kos eller noe annet, svar naturlig på det jeg sa.

Svar kort (1-2 setninger)."""
        else:
            user_prompt = f"""Jeg ({sender_name}, eieren din) sendte deg et bilde uten tekst.

Basert på bildeanalysen viser bildet: {image_description}

Kommenter bildet kort og naturlig. Hvis det er et bilde av deg, gjenkjenn deg selv!

Svar kort (1-2 setninger)."""
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'max_tokens': max_tokens,
                    'temperature': 0.8
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content']
                return ai_response.strip()
            else:
                print(f"⚠️ OpenAI API error: {response.status_code}", flush=True)
                return None
                
        except Exception as e:
            print(f"⚠️ AI response generation failed: {e}", flush=True)
            return None
    
    def generate_conversation_response(
        self,
        user_query: str,
        context: Dict[str, Any] = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 300
    ) -> Optional[str]:
        """
        Generate AI response for general conversation.
        
        Args:
            user_query: User's query/message
            context: Optional context dict (memories, recent messages, etc.)
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
        
        Returns:
            AI response string or None if failed
        """
        system_prompt = f"""Du er {_DUCK_NAME}, en intelligent and-robot. Svar kort, naturlig og med personlighet på norsk."""
        
        # Build context-aware prompt if context provided
        if context:
            context_str = "\n".join([f"- {k}: {v}" for k, v in context.items() if v])
            user_prompt = f"Kontekst:\n{context_str}\n\nSpørsmål: {user_query}"
        else:
            user_prompt = user_query
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'max_tokens': max_tokens,
                    'temperature': 0.8
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                return None
                
        except Exception as e:
            print(f"⚠️ Conversation response failed: {e}", flush=True)
            return None
