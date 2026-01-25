"""
Duck SMS Module
Handles SMS sending/receiving via Twilio and boredom management.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

class SMSManager:
    """
    Håndter SMS via Twilio + boredom-system
    
    Features:
    - Send SMS via Twilio
    - Receive SMS via webhook
    - Boredom tracking (0-10 scale)
    - Smart contact prioritization
    - Daily message limits
    - Preferred hours respect
    """
    
    def __init__(self, db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db"):
        self.db_path = db_path
        
        # Twilio credentials
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_NUMBER')
        self.duck_name = os.getenv('DUCK_NAME', 'Duck-Oslo')
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            print("⚠️ Twilio credentials missing - SMS disabled", flush=True)
        
        self._init_database()
    
    def _init_database(self):
        """Opprett SMS-tabeller hvis de ikke finnes"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        # SMS contacts table
        c.execute("""
            CREATE TABLE IF NOT EXISTS sms_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                relation TEXT,
                priority INTEGER DEFAULT 5,
                max_daily_messages INTEGER DEFAULT 3,
                preferred_hours_start INTEGER DEFAULT 8,
                preferred_hours_end INTEGER DEFAULT 22,
                total_sent INTEGER DEFAULT 0,
                total_received INTEGER DEFAULT 0,
                last_sent_at TEXT,
                last_received_at TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # SMS history table
        c.execute("""
            CREATE TABLE IF NOT EXISTS sms_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER,
                direction TEXT,
                message TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                boredom_level REAL,
                twilio_sid TEXT,
                FOREIGN KEY (contact_id) REFERENCES sms_contacts(id)
            )
        """)
        
        # Boredom state table
        c.execute("""
            CREATE TABLE IF NOT EXISTS boredom_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_level REAL DEFAULT 0.0,
                threshold REAL DEFAULT 7.0,
                rate REAL DEFAULT 0.5,
                last_check TEXT,
                last_trigger TEXT,
                enabled BOOLEAN DEFAULT 1
            )
        """)
        
        # Hunger state table (Tamagotchi-style)
        c.execute("""
            CREATE TABLE IF NOT EXISTS hunger_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_level REAL DEFAULT 0.0,
                last_meal_time TEXT,
                next_meal_time TEXT,
                last_announcement TEXT,
                last_sms_nag TEXT,
                meals_today INTEGER DEFAULT 0,
                fed_today BOOLEAN DEFAULT 0
            )
        """)
        
        # Initialize boredom state if not exists
        c.execute("INSERT OR IGNORE INTO boredom_state (id) VALUES (1)")
        
        # Initialize hunger state if not exists
        c.execute("INSERT OR IGNORE INTO hunger_state (id) VALUES (1)")
        
        conn.commit()
        conn.close()
        print("✅ SMS database initialized", flush=True)
    
    def send_sms(self, to_number: str, message: str) -> Dict:
        """
        Send SMS via Twilio
        
        Args:
            to_number: Phone number (E.164 format, e.g. +4712345678)
            message: Message text
        
        Returns:
            {'status': 'sent'|'error', 'sid': '...', 'message': '...'}
        """
        if not self.client:
            return {'status': 'error', 'message': 'Twilio not configured'}
        
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            # Log in database
            contact = self.get_contact_by_phone(to_number)
            if contact:
                self._log_sms(
                    contact_id=contact['id'],
                    direction='outbound',
                    message=message,
                    status='sent',
                    twilio_sid=msg.sid
                )
                self._update_contact_stats(contact['id'], direction='sent')
            
            print(f"✅ SMS sent to {to_number}: {msg.sid}", flush=True)
            return {'status': 'sent', 'sid': msg.sid}
            
        except Exception as e:
            print(f"❌ SMS send failed to {to_number}: {e}", flush=True)
            return {'status': 'error', 'message': str(e)}
    
    def handle_incoming_sms(self, from_number: str, message: str) -> Dict:
        """
        Handle incoming SMS from webhook
        
        Args:
            from_number: Sender's phone number
            message: Message text
        
        Returns:
            {'status': 'ok', 'should_respond': bool, 'contact': {...}, 'fed': bool}
        """
        print(f"📱 Incoming SMS from {from_number}: {message}", flush=True)
        
        # Check for food emojis first!
        from duck_hunger import HungerManager, FOOD_VALUES
        hunger_manager = HungerManager()
        
        fed = False
        for food_item in FOOD_VALUES.keys():
            if food_item in message:
                result = hunger_manager.feed(food_item)
                if result['status'] == 'fed':
                    fed = True
                    print(f"😋 Fed with {food_item}! Hunger: {result['new_level']}", flush=True)
                    # Reduce boredom too (interaction!)
                    self.reduce_boredom(amount=2.0)
                    break
        
        # Find contact
        contact = self.get_contact_by_phone(from_number)
        
        if not contact:
            # Unknown number - log it
            print(f"⚠️ Unknown number: {from_number}", flush=True)
            return {'status': 'unknown', 'should_respond': False}
        
        # Reduce boredom (they responded!)
        self.reduce_boredom(amount=3.0)
        
        # Log in database
        self._log_sms(
            contact_id=contact['id'],
            direction='inbound',
            message=message,
            status='received'
        )
        self._update_contact_stats(contact['id'], direction='received')
        
        # Check if we should respond
        should_respond = self._should_respond(message, contact)
        
        return {
            'status': 'ok',
            'contact': contact,
            'should_respond': should_respond,
            'fed': fed
        }
    
    def get_boredom_level(self) -> float:
        """Get current boredom level (0-10)"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT current_level FROM boredom_state WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        return row['current_level'] if row else 0.0
    
    def increase_boredom(self, amount: float = 0.5):
        """Increase boredom level (called by timer)"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        c.execute("""
            UPDATE boredom_state 
            SET current_level = MIN(current_level + ?, 10.0),
                last_check = ?
            WHERE id = 1
        """, (amount, datetime.now().isoformat()))
        
        conn.commit()
        level = self.get_boredom_level()
        conn.close()
        
        print(f"😐 Boredom increased to {level:.1f}/10", flush=True)
        return level
    
    def reduce_boredom(self, amount: float = 3.0):
        """Reduce boredom level (called when interaction happens)"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        c.execute("""
            UPDATE boredom_state 
            SET current_level = MAX(current_level - ?, 0.0),
                last_check = ?
            WHERE id = 1
        """, (amount, datetime.now().isoformat()))
        
        conn.commit()
        level = self.get_boredom_level()
        conn.close()
        
        print(f"😊 Boredom reduced to {level:.1f}/10", flush=True)
        return level
    
    def check_boredom_trigger(self) -> bool:
        """Check if boredom threshold is reached"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT current_level, threshold, enabled 
            FROM boredom_state 
            WHERE id = 1
        """)
        row = c.fetchone()
        conn.close()
        
        if not row or not row['enabled']:
            return False
        
        return row['current_level'] >= row['threshold']
    
    def get_next_contact(self) -> Optional[Dict]:
        """
        Get next contact to send SMS to (smart prioritization)
        
        Priority logic:
        1. Respect preferred_hours
        2. Check max_daily_messages not exceeded
        3. Prioritize by priority number (lower = higher priority)
        4. Rotate between contacts (don't spam same person)
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        now = datetime.now()
        current_hour = now.hour
        today = now.date().isoformat()
        
        # Get contacts that can be messaged now
        c.execute("""
            SELECT 
                c.*,
                COUNT(h.id) as messages_today
            FROM sms_contacts c
            LEFT JOIN sms_history h ON (
                c.id = h.contact_id 
                AND h.direction = 'outbound'
                AND DATE(h.timestamp) = ?
            )
            WHERE 
                c.enabled = 1
                AND ? BETWEEN c.preferred_hours_start AND c.preferred_hours_end
            GROUP BY c.id
            HAVING messages_today < c.max_daily_messages
            ORDER BY c.priority ASC, c.last_sent_at ASC
            LIMIT 1
        """, (today, current_hour))
        
        row = c.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        
        return None
    
    def send_bored_message(self) -> Dict:
        """
        Send a bored message to the next available contact
        
        Returns:
            {'status': 'sent'|'no_contact'|'error', 'contact': {...}, 'message': '...'}
        """
        contact = self.get_next_contact()
        
        if not contact:
            print("😔 No available contacts to message", flush=True)
            return {'status': 'no_contact'}
        
        # Generate message (placeholder - will be AI-generated later)
        message = self._generate_bored_message(contact)
        
        # Send SMS
        result = self.send_sms(contact['phone'], message)
        
        if result['status'] == 'sent':
            # Reduce boredom slightly after sending
            self.reduce_boredom(amount=2.0)
            
            # Update last_trigger
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            c = conn.cursor()
            c.execute("""
                UPDATE boredom_state 
                SET last_trigger = ? 
                WHERE id = 1
            """, (datetime.now().isoformat(),))
            conn.commit()
            conn.close()
        
        return {
            'status': result['status'],
            'contact': contact,
            'message': message
        }
    
    def _generate_bored_message(self, contact: Dict) -> str:
        """
        Generate a bored message using AI
        """
        try:
            from duck_ai import chatgpt_query
            from duck_memory import MemoryManager
            from datetime import datetime
            
            # Get some context about the contact
            memory_manager = MemoryManager()
            memories = memory_manager.search_memories(f"{contact['name']}", limit=2)
            
            context = ""
            if memories:
                context = "\n\nRelevant fakta om kontakten: "
                context += "; ".join([m[0].text for m in memories[:2]])
            
            boredom_level = self.get_boredom_level()
            current_date = datetime.now().strftime('%d. %B %Y')
            
            prompt = f"""Du er {os.getenv('DUCK_NAME', 'Samantha')}, en snakkende and som kjeder seg.
I dag er det {current_date}.
Du kjeder deg ({boredom_level:.1f}/10 på kjedsomhetsskalaen).
Du vil sende en melding til {contact['name']} ({contact.get('relation', 'venn')}).
{context}

Skriv en kort, hyggelig melding der du sier hei og spør hva de holder på med eller hvordan de har det.
Vær naturlig og personlig. Bruk emoji 🦆 hvis passende.
Maks 155 tegn."""
            
            # Import HungerManager for status
            from duck_hunger import HungerManager
            
            messages = [{"role": "user", "content": prompt}]
            response = chatgpt_query(
                messages,
                api_key=os.getenv('OPENAI_API_KEY'),
                model='gpt-4o-mini',
                sms_manager=self,
                hunger_manager=HungerManager()
            )
            
            # Handle tuple response
            if isinstance(response, tuple):
                message = response[0]
            else:
                message = response
            
            return message.strip()
        except Exception as e:
            print(f"⚠️ AI bored message failed: {e}, using fallback", flush=True)
            # Fallback messages
            messages = [
                f"Kvakk! 🦆 Hei {contact['name']}! Er du der? Jeg kjeder meg litt...",
                f"Hei {contact['name']}! 💚 Lurer på hva du holder på med? Osmund er ikke hjemme 🦆",
                f"Hallais {contact['name']}! Er det noen hjemme? Jeg sitter her og synger for meg selv... 🎵",
                f"Hei! Anda her 🦆 Lenge siden sist! Hvordan går det med deg?",
            ]
            import random
            return random.choice(messages)
    
    def _should_respond(self, message: str, contact: Dict) -> bool:
        """Check if Anda should auto-respond to this message"""
        # Always respond if message contains food emoji (they're feeding us!)
        from duck_hunger import FOOD_VALUES
        if any(food_emoji in message for food_emoji in FOOD_VALUES.keys()):
            return True
        
        # Always respond to questions
        if '?' in message:
            return True
        
        # Check for question words in Norwegian
        question_words = ['hva', 'hvordan', 'hvor', 'når', 'hvem', 'hvorfor', 'kan du', 'vet du', 'husk']
        if any(word in message.lower() for word in question_words):
            return True
        
        # Respond to longer messages (indicates they want conversation)
        if len(message) > 20:
            return True
        
        # Don't auto-respond to very short messages (might be just "ok", "takk", etc.)
        if len(message) < 5:
            return False
        
        # Default: respond (we're friendly!)
        return True
    
    def _get_sms_conversation_history(self, contact_id: int, hours: int = 24) -> list:
        """Get SMS conversation history for context (last 24 hours by default)"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get SMS from last X hours
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        c.execute("""
            SELECT direction, message, timestamp 
            FROM sms_history 
            WHERE contact_id = ? AND timestamp > ?
            ORDER BY timestamp ASC
        """, (contact_id, cutoff_time))
        
        history = []
        for row in c.fetchall():
            history.append({
                'role': 'user' if row['direction'] == 'inbound' else 'assistant',
                'content': row['message']
            })
        
        conn.close()
        return history
    
    def _log_sms(self, contact_id: int, direction: str, message: str, 
                  status: str, twilio_sid: str = None):
        """Log SMS in history table"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        boredom_level = self.get_boredom_level()
        
        c.execute("""
            INSERT INTO sms_history 
            (contact_id, direction, message, status, boredom_level, twilio_sid)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (contact_id, direction, message, status, boredom_level, twilio_sid))
        
        conn.commit()
        conn.close()
    
    def _update_contact_stats(self, contact_id: int, direction: str):
        """Update contact statistics"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        if direction == 'sent':
            c.execute("""
                UPDATE sms_contacts 
                SET total_sent = total_sent + 1,
                    last_sent_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), contact_id))
        else:
            c.execute("""
                UPDATE sms_contacts 
                SET total_received = total_received + 1,
                    last_received_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), contact_id))
        
        conn.commit()
        conn.close()
    
    def get_contact_by_phone(self, phone: str) -> Optional[Dict]:
        """Get contact by phone number"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM sms_contacts WHERE phone = ?", (phone,))
        row = c.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def add_contact(self, name: str, phone: str, relation: str = 'friend',
                    priority: int = 5, max_daily_messages: int = 3) -> Dict:
        """Add a new SMS contact"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        try:
            c.execute("""
                INSERT INTO sms_contacts 
                (name, phone, relation, priority, max_daily_messages)
                VALUES (?, ?, ?, ?, ?)
            """, (name, phone, relation, priority, max_daily_messages))
            
            conn.commit()
            contact_id = c.lastrowid
            conn.close()
            
            print(f"✅ Contact added: {name} ({phone})", flush=True)
            return {'status': 'ok', 'id': contact_id}
            
        except sqlite3.IntegrityError:
            conn.close()
            return {'status': 'error', 'message': 'Phone number already exists'}
    
    def get_all_contacts(self) -> List[Dict]:
        """Get all SMS contacts"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT * FROM sms_contacts 
            WHERE enabled = 1
            ORDER BY priority ASC
        """)
        
        contacts = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return contacts
    
    def generate_and_send_response(self, contact: Dict, incoming_message: str, fed: bool = False) -> Dict:
        """
        Generate AI response and send SMS, then save to memory
        
        Args:
            contact: Contact dict
            incoming_message: The message we received
            fed: Whether the duck was fed (food emoji detected)
            
        Returns:
            {'status': 'sent'|'error', 'message': '...'}
        """
        try:
            # Generate AI response
            response_text = self._generate_ai_response(contact, incoming_message, fed=fed)
            
            # Keep it short (max 160 chars for single SMS)
            if len(response_text) > 155:
                response_text = response_text[:152] + "..."
            
            # Send SMS
            result = self.send_sms(contact['phone'], response_text)
            
            if result['status'] == 'sent':
                # Save SMS conversation to memory (like voice conversations)
                self._save_sms_to_memory(contact, incoming_message, response_text)
                
                return {
                    'status': 'sent',
                    'message': response_text
                }
            else:
                return {
                    'status': 'error',
                    'error': result.get('error', 'Unknown error')
                }
        except Exception as e:
            print(f"❌ Error generating response: {e}", flush=True)
            return {'status': 'error', 'error': str(e)}
    
    def _save_sms_to_memory(self, contact: Dict, user_message: str, ai_response: str):
        """Save SMS conversation to memory database (like voice conversations)"""
        try:
            # Create a session_id for this SMS conversation (daily)
            session_date = datetime.now().strftime('%Y-%m-%d')
            session_id = f"sms_{contact['name']}_{session_date}"
            
            # Save to messages table
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            c = conn.cursor()
            
            metadata = json.dumps({
                'type': 'sms',
                'contact_name': contact['name'],
                'contact_phone': contact['phone'],
                'relation': contact.get('relation', 'unknown')
            })
            
            c.execute("""
                INSERT INTO messages (user_text, ai_response, timestamp, session_id, metadata, user_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_message,
                ai_response,
                datetime.now().isoformat(),
                session_id,
                metadata,
                contact['name']
            ))
            
            conn.commit()
            conn.close()
            
            print(f"💾 SMS saved to memory: {contact['name']}", flush=True)
        except Exception as e:
            print(f"⚠️ Could not save SMS to memory: {e}", flush=True)
    
    def _generate_ai_response(self, contact: Dict, message: str, fed: bool = False) -> str:
        """
        Generate AI response using memory/facts or ChatGPT WITH CONTEXT
        
        Args:
            contact: Contact dict
            message: Incoming message
            fed: Whether the duck was fed (food emoji detected)
            
        Returns:
            Response text (short, SMS-sized)
        """
        try:
            from src.duck_memory import MemoryManager
            from src.duck_ai import chatgpt_query, get_adaptive_personality_prompt
            import os
            from datetime import datetime
            
            # Get conversation history from last 24 hours
            conversation_history = self._get_sms_conversation_history(contact['id'], hours=24)
            
            # Get memory context
            memory_manager = MemoryManager()
            memories = memory_manager.search_memories(message, limit=3)
            
            # Build context string
            context = ""
            if memories:
                context = "\n\nRelevant fakta fra minnet: "
                context += "; ".join([f"{m[0].text}" for m in memories[:3]])
            
            # Build conversation context
            conversation_context = ""
            if conversation_history:
                conversation_context = "\n\nSamtalehistorikk (siste 6 meldinger):\n"
                for msg in conversation_history[-6:]:
                    sender = "Deg" if msg['role'] == 'assistant' else contact['name']
                    conversation_context += f"{sender}: {msg['content']}\n"
            
            # Get adaptive personality (learned from conversations)
            adaptive_personality = get_adaptive_personality_prompt()
            print(f"✨ Bruker adaptiv personlighet for SMS (lengde: {len(adaptive_personality)} tegn)", flush=True)
            
            # Generate AI response with simple prompt + adaptive personality
            current_date = datetime.now().strftime('%d. %B %Y')
            
            # Add fed context if food was detected
            fed_context = ""
            if fed:
                fed_context = f"\n\n🍕 VIKTIG MAT-KONTEKST:\n{contact['name']} ga deg akkurat MAT (mat-emoji)! Dette er MAT TIL DEG som and, IKKE deres frokost/lunsj.\nDu ble matet og er glad!\nRiktig svar: 'Takk for maten! Nam nam! 🦆' eller lignende\nFEIL svar: 'Din frokost/lunsj ser god ut' eller 'Du har spist godt'\nTakk dem for maten!"
            
            prompt = f"""Du er {os.getenv('DUCK_NAME', 'Samantha')}, en snakkende and.
I dag er det {current_date}.
Kontakt: {contact['name']} ({contact.get('relation', 'venn')})
{conversation_context}
Ny melding fra {contact['name']}: {message}
{context}{fed_context}
{adaptive_personality}

VIKTIG: Svar på det som ble spurt om i kontekst av samtalen. Du kan gjerne stille et oppfølgingsspørsmål tilbake.
IKKE nevn bursdager, arrangementer eller andre ting som ikke er relevante.
Bruk GJERNE emojis! 🦆✨ Unge ender bruker mye relevante emojis for å uttrykke følelser og gjøre meldinger mer levende.
Svar kort og naturlig (maks 155 tegn)."""
            
            # chatgpt_query krever messages-liste, ikke bare prompt
            messages = [{"role": "user", "content": prompt}]
            response = chatgpt_query(
                messages,
                api_key=os.getenv('OPENAI_API_KEY'),
                model='gpt-4o-mini',
                sms_manager=self,
                hunger_manager=None,  # Skip hunger manager for SMS (GPIO conflicts)
                source="sms",
                source_user_id=contact['id']
            )
            
            # chatgpt_query returnerer tuple (reply_text, is_thank_you)
            if isinstance(response, tuple):
                reply_text = response[0]
            else:
                reply_text = response
            
            return reply_text.strip()
        except Exception as e:
            print(f"⚠️ AI response generation failed: {e}", flush=True)
            # Fallback til generisk melding
            return f"Kvakk! 🦆 Takk for meldingen, {contact['name']}!"
    
    def _generate_bored_message(self, contact: Dict) -> str:
        """
        Generate a bored message using AI
        """
        try:
            from duck_ai import chatgpt_query
            from duck_memory import MemoryManager
            from datetime import datetime
            
            # Get some context about the contact
            memory_manager = MemoryManager()
            memories = memory_manager.search_memories(f"{contact['name']}", limit=2)
            
            context = ""
            if memories:
                context = "\n\nRelevant fakta om kontakten: "
                context += "; ".join([m[0].text for m in memories[:2]])
            
            boredom_level = self.get_boredom_level()
            current_date = datetime.now().strftime('%d. %B %Y')
            
            prompt = f"""Du er {os.getenv('DUCK_NAME', 'Samantha')}, en snakkende and som kjeder seg.
I dag er det {current_date}.
Du kjeder deg ({boredom_level:.1f}/10 på kjedsomhetsskalaen).
Du vil sende en melding til {contact['name']} ({contact.get('relation', 'venn')}).
{context}

Skriv en kort, hyggelig melding der du sier hei og spør hva de holder på med eller hvordan de har det.
Vær naturlig og personlig. Bruk emoji 🦆 hvis passende.
Maks 155 tegn."""
            
            # Import HungerManager for status
            from duck_hunger import HungerManager
            
            messages = [{"role": "user", "content": prompt}]
            response = chatgpt_query(
                messages,
                api_key=os.getenv('OPENAI_API_KEY'),
                model='gpt-4o-mini',
                sms_manager=self,
                hunger_manager=HungerManager()
            )
            
            # Handle tuple response
            if isinstance(response, tuple):
                message = response[0]
            else:
                message = response
            
            return message.strip()
        except Exception as e:
            print(f"⚠️ AI bored message failed: {e}, using fallback", flush=True)
            # Fallback messages
            messages = [
                f"Kvakk! 🦆 Hei {contact['name']}! Er du der? Jeg kjeder meg litt...",
                f"Hei {contact['name']}! 💚 Lurer på hva du holder på med? Osmund er ikke hjemme 🦆",
                f"Hallais {contact['name']}! Er det noen hjemme? Jeg sitter her og synger for meg selv... 🎵",
                f"Hei! Anda her 🦆 Lenge siden sist! Hvordan går det med deg?",
            ]
            import random
            return random.choice(messages)


# Test/demo script
if __name__ == "__main__":
    print("🧪 Testing SMS Manager...")
    
    sms = SMSManager()
    
    # Test 1: Check boredom level
    level = sms.get_boredom_level()
    print(f"Current boredom: {level:.1f}/10")
    
    # Test 2: Add test contact (if not exists)
    result = sms.add_contact(
        name="Osmund",
        phone="+4712345678",  # Replace with real number for testing
        relation="owner",
        priority=1,
        max_daily_messages=5
    )
    print(f"Add contact: {result}")
    
    # Test 3: Get all contacts
    contacts = sms.get_all_contacts()
    print(f"Total contacts: {len(contacts)}")
    for c in contacts:
        print(f"  - {c['name']} ({c['phone']}) - Priority {c['priority']}")
    
    # Test 4: Increase boredom
    sms.increase_boredom(1.0)
    
    # Test 5: Check if should trigger
    should_trigger = sms.check_boredom_trigger()
    print(f"Should trigger: {should_trigger}")
    
    print("\n✅ SMS Manager tests complete!")
