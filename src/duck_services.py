"""
Duck Services Manager
Singleton som holder alle service-instanser i minnet for å unngå re-initialisering.
"""
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Ensure src is in path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Import all managers
from duck_memory import MemoryManager
from duck_user_manager import UserManager
from duck_sms import SMSManager
from duck_vision import VisionAnalyzer, VisionConfig
from duck_hunger import HungerManager
from duck_ai_response import AIResponseGenerator

# Load environment
load_dotenv()


class ServiceManager:
    """
    Singleton som holder alle service-instanser.
    Unngår re-initialisering og database-locking.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize all services once"""
        if self._initialized:
            return
        
        # Database path
        project_root = Path(__file__).parent.parent
        self.db_path = str(project_root / 'duck_memory.db')
        
        # Initialize managers
        print("🔧 Initializing ServiceManager...", flush=True)
        
        self.memory_manager = MemoryManager(db_path=self.db_path)
        self.user_manager = UserManager(db_path=self.db_path)
        self.sms_manager = SMSManager(db_path=self.db_path)
        self.hunger_manager = HungerManager(db_path=self.db_path)
        
        # Vision requires API key
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and VisionConfig.ENABLED:
            self.vision_analyzer = VisionAnalyzer(api_key)
            self.ai_response_generator = AIResponseGenerator(api_key)
        else:
            self.vision_analyzer = None
            self.ai_response_generator = None
        
        self._initialized = True
        print("✅ ServiceManager initialized", flush=True)
    
    def get_memory_manager(self) -> MemoryManager:
        """Get MemoryManager instance"""
        return self.memory_manager
    
    def get_user_manager(self) -> UserManager:
        """Get UserManager instance"""
        return self.user_manager
    
    def get_sms_manager(self) -> SMSManager:
        """Get SMSManager instance"""
        return self.sms_manager
    
    def get_hunger_manager(self) -> HungerManager:
        """Get HungerManager instance"""
        return self.hunger_manager
    
    def get_vision_analyzer(self) -> Optional[VisionAnalyzer]:
        """Get VisionAnalyzer instance (None if disabled or no API key)"""
        return self.vision_analyzer
    
    def get_ai_response_generator(self) -> Optional[AIResponseGenerator]:
        """Get AIResponseGenerator instance (None if no API key)"""
        return self.ai_response_generator


# Global singleton instance
_service_manager = None


def get_services() -> ServiceManager:
    """
    Get the global ServiceManager singleton.
    
    Returns:
        ServiceManager: The singleton instance with all initialized services
    """
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
