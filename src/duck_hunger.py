"""
Duck Hunger System - Tamagotchi-style feeding mechanics

Handles:
- Hunger tracking (increases every hour)
- Meal times (12:00, 17:00, 21:00)
- Food types (🍪 cookie = 5 points, 🍕 pizza = 10 points)
- Announcements when hungry
- Auto-SMS nagging to contacts
- Personality impact (grumpy when hungry)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import json
import os

# Food values (halved to require more feeding, like a real Tamagotchi)
FOOD_VALUES = {
    '🍪': 2.5,   # Cookie
    '🍰': 2.5,   # Cake
    '🍎': 2.5,   # Apple
    '🍌': 2.5,   # Banana
    '🍕': 5,     # Pizza
    'cookie': 2.5,
    'cake': 2.5,
    'apple': 2.5,
    'banana': 2.5,
    'pizza': 5
}

# Meal times (24-hour format)
MEAL_TIMES = [12, 17, 21]  # 12:00, 17:00, 21:00

# Hunger thresholds
HUNGER_THRESHOLD = 7.0  # When Anda starts complaining
HUNGER_MAX = 10.0


class HungerManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'duck_memory.db'
        self.db_path = str(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """Ensure hunger_state table exists"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
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
        
        c.execute("INSERT OR IGNORE INTO hunger_state (id) VALUES (1)")
        conn.commit()
        conn.close()
    
    def get_hunger_level(self) -> float:
        """Get current hunger level (0-10)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT current_level FROM hunger_state WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        return row['current_level'] if row else 0.0
    
    def increase_hunger(self, amount: float = 1.0):
        """Increase hunger level (called every hour)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE hunger_state 
            SET current_level = MIN(current_level + ?, ?)
            WHERE id = 1
        """, (amount, HUNGER_MAX))
        
        conn.commit()
        level = self.get_hunger_level()
        conn.close()
        
        print(f"🍽️ Hunger increased to {level:.1f}/10", flush=True)
        return level
    
    def feed(self, food_type: str) -> Dict:
        """
        Feed Anda with food
        
        Args:
            food_type: '🍪', '🍕', 'cookie', or 'pizza'
        
        Returns:
            {'status': 'fed', 'hunger_reduced': float, 'new_level': float}
        """
        if food_type not in FOOD_VALUES:
            return {'status': 'unknown_food', 'message': f"Jeg kjenner ikke {food_type}"}
        
        value = FOOD_VALUES[food_type]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Reduce hunger
        c.execute("""
            UPDATE hunger_state 
            SET current_level = MAX(current_level - ?, 0.0),
                last_meal_time = ?,
                meals_today = meals_today + 1,
                fed_today = 1
            WHERE id = 1
        """, (value, datetime.now().isoformat()))
        
        conn.commit()
        new_level = self.get_hunger_level()
        conn.close()
        
        food_emoji = food_type if food_type in ['🍪', '🍕'] else ('🍪' if food_type == 'cookie' else '🍕')
        print(f"😋 Fed with {food_emoji}! Hunger reduced to {new_level:.1f}/10", flush=True)
        
        return {
            'status': 'fed',
            'food': food_emoji,
            'hunger_reduced': value,
            'new_level': new_level
        }
    
    def is_hungry(self) -> bool:
        """Check if Anda is hungry (above threshold)"""
        return self.get_hunger_level() >= HUNGER_THRESHOLD
    
    def is_meal_time(self) -> bool:
        """Check if it's one of the meal times"""
        current_hour = datetime.now().hour
        return current_hour in MEAL_TIMES
    
    def get_next_meal_time(self) -> Optional[str]:
        """Get next meal time"""
        current_hour = datetime.now().hour
        
        for meal_hour in MEAL_TIMES:
            if meal_hour > current_hour:
                return f"{meal_hour:02d}:00"
        
        # Next meal is tomorrow at 12:00
        return "12:00 (i morgen)"
    
    def should_announce_hunger(self) -> bool:
        """Check if we should announce hunger (30 min since last meal time without food)"""
        if not self.is_hungry():
            return False
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT last_meal_time, last_announcement FROM hunger_state WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        if not row:
            return False
        
        # Check if it's been 30 min since a meal time
        current_time = datetime.now()
        current_hour = current_time.hour
        
        if current_hour in MEAL_TIMES:
            # At meal time - check if 30 min passed
            meal_time = current_time.replace(minute=0, second=0, microsecond=0)
            time_since_meal = (current_time - meal_time).total_seconds() / 60
            
            if time_since_meal >= 30:
                # Check last announcement
                if row['last_announcement']:
                    last_announcement = datetime.fromisoformat(row['last_announcement'])
                    time_since_announcement = (current_time - last_announcement).total_seconds() / 60
                    
                    # Don't announce more than once per 30 min
                    if time_since_announcement < 30:
                        return False
                
                return True
        
        return False
    
    def mark_announcement_made(self):
        """Mark that we made a hunger announcement"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE hunger_state 
            SET last_announcement = ?
            WHERE id = 1
        """, (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()
    
    def should_send_sms_nag(self) -> bool:
        """Check if we should send SMS nag (10 min after last SMS or announcement)"""
        if not self.is_hungry():
            return False
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT last_announcement, last_sms_nag FROM hunger_state WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        if not row:
            return False
        
        current_time = datetime.now()
        
        # Check if we've announced first
        if not row['last_announcement']:
            return False
        
        # Check time since last SMS nag or announcement
        reference_time = row['last_sms_nag'] if row['last_sms_nag'] else row['last_announcement']
        if reference_time:
            last_time = datetime.fromisoformat(reference_time)
            minutes_since = (current_time - last_time).total_seconds() / 60
            
            # Send SMS every 10 min after announcement
            return minutes_since >= 10
        
        return False
    
    def mark_sms_nag_sent(self):
        """Mark that we sent SMS nag"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE hunger_state 
            SET last_sms_nag = ?
            WHERE id = 1
        """, (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()
    
    def reset_daily(self):
        """Reset hunger for new day (called at morning)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE hunger_state 
            SET current_level = 0.0,
                meals_today = 0,
                fed_today = 0,
                last_meal_time = ?,
                last_announcement = NULL,
                last_sms_nag = NULL
            WHERE id = 1
        """, (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()
        
        print("🌅 Morning! Anda found breakfast herself - not hungry", flush=True)
    
    def get_hunger_mood(self) -> str:
        """Get mood based on hunger level (for personality system)"""
        level = self.get_hunger_level()
        
        if level < 3:
            return "content"  # Fornøyd
        elif level < 5:
            return "neutral"  # Nøytral
        elif level < 7:
            return "hungry"   # Sulten
        elif level < 9:
            return "grumpy"   # Gretten
        else:
            return "hangry"   # VELDIG gretten
    
    def get_status(self) -> Dict:
        """Get complete hunger status"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM hunger_state WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        if not row:
            return {}
        
        level = row['current_level']
        mood = self.get_hunger_mood()
        next_meal = self.get_next_meal_time()
        
        return {
            'level': round(level, 1),
            'mood': mood,
            'is_hungry': level >= HUNGER_THRESHOLD,
            'meals_today': row['meals_today'],
            'last_meal_time': row['last_meal_time'],
            'next_meal_time': next_meal
        }
    
    def get_last_meal_info(self) -> Dict:
        """Get info about last meal for AI awareness"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT last_meal_time, meals_today FROM hunger_state WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
        if not row or not row['last_meal_time']:
            return {
                'ate_today': False,
                'food_emoji': '',
                'food_name': '',
                'time': '',
                'next_meal_time': self.get_next_meal_time()
            }
        
        last_meal_time = datetime.fromisoformat(row['last_meal_time'])
        today = datetime.now().date()
        ate_today = last_meal_time.date() == today
        
        # Try to determine what was eaten (this is simplified - could be enhanced)
        # For now, just show generic food
        return {
            'ate_today': ate_today,
            'food_emoji': '🍕',  # Could be tracked better
            'food_name': 'mat',
            'time': last_meal_time.strftime('%H:%M'),
            'next_meal_time': self.get_next_meal_time()
        }


if __name__ == "__main__":
    print("🧪 Testing Hunger Manager...")
    
    hm = HungerManager()
    
    print(f"Current hunger: {hm.get_hunger_level()}")
    print(f"Is meal time? {hm.is_meal_time()}")
    print(f"Next meal: {hm.get_next_meal_time()}")
    
    # Test feeding
    result = hm.feed('🍪')
    print(f"Fed cookie: {result}")
    
    result = hm.feed('🍕')
    print(f"Fed pizza: {result}")
    
    print("✅ Hunger Manager tests complete!")
