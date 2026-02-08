"""
Duck-Vision Service
Håndterer MQTT kommunikasjon med Duck-Vision kamera på Pi 5
"""
import logging
from typing import Optional, Callable
from src.duck_vision_integration import DuckVisionHandler

logger = logging.getLogger(__name__)


class DuckVisionService:
    """
    Service for MQTT kommunikasjon med Duck-Vision kamera.
    Integreres i ServiceManager for å håndtere face recognition og object detection.
    
    Delegerer all MQTT-kommunikasjon til DuckVisionHandler som håndterer:
    - Auto-reconnect ved nettverksproblemer
    - LWT (Last Will and Testament) for pålitelig status
    - threading.Event for effektiv synkron venting
    - QoS 1 for kommandoer
    """
    
    def __init__(self, broker_host: str = "oDuckberry-vision.local", broker_port: int = 1883):
        """
        Initialize Duck-Vision service
        
        Args:
            broker_host: MQTT broker address (default: "oDuckberry-vision.local")
            broker_port: MQTT broker port (default: 1883)
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.vision_handler: Optional[DuckVisionHandler] = None
        
        # Callbacks
        self.on_face_detected_callback = None
        self.on_unknown_face_callback = None
        self.on_learning_progress_callback = None
        self.on_speaker_recognized_callback = None
        self.on_voice_learned_callback = None
        
        logger.info(f"DuckVisionService initialized (broker: {broker_host}:{broker_port})")
    
    def start(self, 
              on_face_detected: Optional[Callable] = None,
              on_unknown_face: Optional[Callable] = None,
              on_learning_progress: Optional[Callable] = None,
              on_speaker_recognized: Optional[Callable] = None,
              on_voice_learned: Optional[Callable] = None) -> bool:
        """
        Start the Duck-Vision service and connect to MQTT broker
        
        Args:
            on_face_detected: Callback when known face is detected (name, confidence)
            on_unknown_face: Callback when unknown face is detected ()
            on_learning_progress: Callback during face learning (name, step, total, instruction)
            on_speaker_recognized: Callback when voice is recognized (name, confidence)
            on_voice_learned: Callback when voice profile is created (name, success)
        
        Returns:
            bool: True if successfully connected, False otherwise
        """
        # Store callbacks
        self.on_face_detected_callback = on_face_detected
        self.on_unknown_face_callback = on_unknown_face
        self.on_learning_progress_callback = on_learning_progress
        self.on_speaker_recognized_callback = on_speaker_recognized
        self.on_voice_learned_callback = on_voice_learned
        
        try:
            # Initialize handler with callbacks
            self.vision_handler = DuckVisionHandler(
                broker_host=self.broker_host,
                broker_port=self.broker_port,
                on_face_detected=self._on_face_detected_internal,
                on_unknown_face=self._on_unknown_face_internal,
                on_object_detected=self._on_object_detected_internal,
                on_learning_progress=on_learning_progress,  # Pass through to handler
                on_speaker_recognized=self._on_speaker_recognized_internal,
                on_voice_learned=self._on_voice_learned_internal
            )
            
            # Connect to MQTT broker
            if self.vision_handler.connect():
                logger.info("Duck-Vision service started successfully")
                return True
            else:
                logger.warning("Duck-Vision service could not connect to MQTT broker")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to start Duck-Vision service: {e}")
            return False
    
    def stop(self):
        """Stop the Duck-Vision service and disconnect from MQTT broker"""
        if self.vision_handler:
            try:
                self.vision_handler.disconnect()
                logger.info("Duck-Vision service stopped")
            except Exception as e:
                logger.error(f"Error stopping Duck-Vision service: {e}")
    
    def _on_object_detected_internal(self, object_name: str, confidence: float):
        """Internal callback for object detection - logged for debugging."""
        logger.debug(f"Object detected: {object_name} ({confidence:.2%})")
    
    def _on_face_detected_internal(self, person_name: Optional[str], confidence: float):
        """Internal callback for face detection - forwards to external callback."""
        logger.debug(f"Face detected: {person_name or 'unknown'} ({confidence:.2%})")
        if person_name and self.on_face_detected_callback:
            self.on_face_detected_callback(person_name, confidence)
    
    def _on_unknown_face_internal(self):
        """Internal callback for unknown face detection - forwards to external callback."""
        logger.debug("Unknown face detected")
        if self.on_unknown_face_callback:
            self.on_unknown_face_callback()
    
    def _on_speaker_recognized_internal(self, name: str, confidence: float):
        """Internal callback for speaker recognition - forwards to external callback."""
        logger.info(f"🔊 Speaker recognized: {name} ({confidence:.2%})")
        if self.on_speaker_recognized_callback:
            self.on_speaker_recognized_callback(name, confidence)
    
    def _on_voice_learned_internal(self, name: str, success: bool):
        """Internal callback for voice profile creation - forwards to external callback."""
        if success:
            logger.info(f"✅ Voice profile created for {name}")
        else:
            logger.warning(f"❌ Voice profile creation failed for {name}")
        if self.on_voice_learned_callback:
            self.on_voice_learned_callback(name, success)
    
    # Commands to Duck-Vision
    
    def look_around(self, timeout: float = 10.0) -> Optional[str]:
        """
        Synkron metode for å se hva som er rundt Duck-Vision (IMX500 - 0.6ms).
        Delegerer til DuckVisionHandler.look_around() som håndterer alt.
        
        Args:
            timeout: Hvor lenge å vente på svar (sekunder)
        
        Returns:
            str: Beskrivelse av hva som ble sett (f.eks. "Jeg ser en person, en laptop og en mus")
        """
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot look around")
            return None
        
        # Use the handler's look_around method directly
        logger.info(f"Calling Duck-Vision look_around (timeout: {timeout}s)")
        result = self.vision_handler.look_around(timeout=timeout)
        logger.info(f"Duck-Vision response: {result}")
        return result
    
    def analyze_scene(self, question: Optional[str] = None, timeout: float = 15.0) -> Optional[str]:
        """
        Synkron metode for dyp scene-analyse med OpenAI Vision (~5s).
        
        Bruk denne når du trenger:
        - Detaljert beskrivelse av scene
        - Farger, aktiviteter, stemninger
        - Komplekse spørsmål om bildet
        
        Args:
            question: Spesifikt spørsmål (valgfritt)
            timeout: Hvor lenge å vente på svar (sekunder, OpenAI tar vanligvis 2-5s)
        
        Returns:
            str: Detaljert beskrivelse fra OpenAI Vision
        """
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot analyze scene")
            return None
        
        logger.info(f"Calling Duck-Vision analyze_scene (question: {question}, timeout: {timeout}s)")
        result = self.vision_handler.analyze_scene(question=question, timeout=timeout)
        logger.info(f"Duck-Vision OpenAI response length: {len(result) if result else 0} chars")
        return result
    
    def request_object_detection(self):
        """
        Request object detection from Duck-Vision (async).
        Results arrive via the handler's callback.
        """
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot request object detection")
            return
        
        self.vision_handler.request_object_detection()
        logger.debug("Requested object detection from Duck-Vision")
    
    def learn_person(self, name: str, num_samples: int = 5):
        """Tell Duck-Vision to learn a new person"""
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot learn person")
            return
        self.vision_handler.learn_person(name, num_samples)
        logger.info(f"Requested Duck-Vision to learn: {name} ({num_samples} samples)")
    
    def check_person(self, timeout: float = 3.0):
        """
        Check who is in front of the camera (synkron).
        Returns tuple: (found, name, confidence)
        """
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot check person")
            return (False, None, 0.0)
        result = self.vision_handler.check_person(timeout=timeout)
        logger.info(f"check_person result: {result}")
        return result
    
    def forget_person(self, name: str):
        """Tell Duck-Vision to forget a person"""
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot forget person")
            return
        self.vision_handler.forget_person(name)
        logger.info(f"Requested Duck-Vision to forget: {name}")
    
    def list_known_people(self):
        """Tell Duck-Vision to list all known people"""
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot list people")
            return
        self.vision_handler.list_known_people()
        logger.info("Requested list of known people")
    
    def learn_voice(self, name: str, duration: float = 10.0):
        """Tell Duck-Vision to learn a person's voice manually"""
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot learn voice")
            return
        self.vision_handler.learn_voice(name, duration)
        logger.info(f"Requested Duck-Vision to learn voice: {name} ({duration}s)")
    
    def notify_speaking(self, speaking: bool):
        """Mute/unmute Duck-Vision mic when Samantha speaks/stops speaking"""
        if self.vision_handler:
            self.vision_handler.notify_speaking(speaking)

    def notify_conversation(self, active: bool):
        """Signal to Duck-Vision that a conversation is active/ended"""
        if self.vision_handler:
            self.vision_handler.notify_conversation(active)

    def save_conversation_voice(self, name: str):
        """Ask Duck-Vision to save a voice profile from conversation audio"""
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot save conversation voice")
            return
        self.vision_handler.save_conversation_voice(name)
        logger.info(f"Requested Duck-Vision to save conversation voice for: {name}")
    
    def is_connected(self) -> bool:
        """Check if Duck-Vision on Pi 5 is actually online and reachable"""
        return bool(
            self.vision_handler 
            and self.vision_handler.connected 
            and self.vision_handler.publisher_online
        )
