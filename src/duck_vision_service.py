"""
Duck-Vision Service
Håndterer MQTT kommunikasjon med Duck-Vision kamera på Pi 5
"""
import logging
from typing import Optional, Callable
from queue import Queue, Empty
import threading
from src.duck_vision_integration import DuckVisionHandler

logger = logging.getLogger(__name__)


class DuckVisionService:
    """
    Service for MQTT kommunikasjon med Duck-Vision kamera.
    Integreres i ServiceManager for å håndtere face recognition og object detection.
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
        self.connected = False
        
        # Callbacks
        self.on_face_detected_callback = None
        self.on_unknown_face_callback = None
        self.on_learning_progress_callback = None
        
        # Queue for object detection results (for AI tool)
        self.object_detection_queue = Queue(maxsize=1)
        self.face_detection_queue = Queue(maxsize=1)
        self._detection_timeout = 3.0  # seconds
        
        logger.info(f"DuckVisionService initialized (broker: {broker_host}:{broker_port})")
    
    def start(self, 
              on_face_detected: Optional[Callable] = None,
              on_unknown_face: Optional[Callable] = None,
              on_learning_progress: Optional[Callable] = None) -> bool:
        """
        Start the Duck-Vision service and connect to MQTT broker
        
        Args:
            on_face_detected: Callback when known face is detected (name, confidence)
            on_unknown_face: Callback when unknown face is detected ()
            on_learning_progress: Callback during face learning (name, step, total, instruction)
        
        Returns:
            bool: True if successfully connected, False otherwise
        """
        # Store callbacks
        self.on_face_detected_callback = on_face_detected
        self.on_unknown_face_callback = on_unknown_face
        self.on_learning_progress_callback = on_learning_progress
        
        try:
            # Initialize handler with callbacks
            self.vision_handler = DuckVisionHandler(
                broker_host=self.broker_host,
                broker_port=self.broker_port,
                on_face_detected=self._on_face_detected_internal,
                on_unknown_face=self._on_unknown_face_internal,
                on_object_detected=self._on_object_detected_internal,
                on_learning_progress=on_learning_progress  # Pass through to handler
            )
            
            # Connect to MQTT broker
            if self.vision_handler.connect():
                self.connected = True
                logger.info("✓ Duck-Vision service started successfully")
                return True
            else:
                logger.warning("⚠️ Duck-Vision service could not connect to MQTT broker")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to start Duck-Vision service: {e}")
            return False
    
    def stop(self):
        """Stop the Duck-Vision service and disconnect from MQTT broker"""
        if self.vision_handler:
            try:
                self.vision_handler.disconnect()
                self.connected = False
                logger.info("Duck-Vision service stopped")
            except Exception as e:
                logger.error(f"Error stopping Duck-Vision service: {e}")
    
    def _on_object_detected_internal(self, object_name: str, confidence: float):
        """
        Internal callback for object detection.
        Puts result in queue for AI tool to consume.
        """
        result = {
            'type': 'object',
            'object_name': object_name,
            'confidence': confidence
        }
        
        # Put in queue (overwrite old result if queue is full)
        try:
            self.object_detection_queue.get_nowait()  # Clear old result
        except Empty:
            pass
        
        self.object_detection_queue.put(result)
        logger.debug(f"Object detected: {object_name} ({confidence:.2%})")
    
    def _on_face_detected_internal(self, person_name: Optional[str], confidence: float):
        """
        Internal callback for face detection.
        Puts result in queue for AI tool to consume.
        """
        result = {
            'type': 'face',
            'person_name': person_name,
            'is_known': person_name is not None,
            'confidence': confidence
        }
        
        # Put in face queue
        try:
            self.face_detection_queue.get_nowait()
        except Empty:
            pass
        
        self.face_detection_queue.put(result)
        logger.debug(f"Face detected: {person_name or 'unknown'} ({confidence:.2%})")
        
        # Call external callback
        if person_name and self.on_face_detected_callback:
            self.on_face_detected_callback(person_name, confidence)
    
    def _on_unknown_face_internal(self):
        """
        Internal callback for unknown face detection.
        """
        result = {
            'type': 'face',
            'person_name': None,
            'is_known': False,
            'confidence': 0.0
        }
        
        # Put in face queue
        try:
            self.face_detection_queue.get_nowait()
        except Empty:
            pass
        
        self.face_detection_queue.put(result)
        logger.debug("Unknown face detected")
        
        # Call external callback
        if self.on_unknown_face_callback:
            self.on_unknown_face_callback()
    
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
    
    def request_object_detection(self) -> Optional[dict]:
        """
        Request object detection from Duck-Vision and wait for result.
        Used by AI tool 'look_around()'.
        
        Returns:
            dict: {'object_name': str, 'confidence': float} or None if timeout
        """
        if not self.is_connected():
            logger.warning("Duck-Vision not connected, cannot request object detection")
            return None
        
        # Clear queue
        try:
            self.object_detection_queue.get_nowait()
        except Empty:
            pass
        
        # Send command to Duck-Vision
        self.vision_handler.request_object_detection()
        logger.debug("Requested object detection from Duck-Vision")
        
        # Wait for result
        try:
            result = self.object_detection_queue.get(timeout=self._detection_timeout)
            logger.info(f"Got object detection result: {result['object_name']}")
            return result
        except Empty:
            logger.warning(f"Object detection timed out after {self._detection_timeout}s")
            return None
    
    def learn_person(self, name: str, num_samples: int = 5):
        """
        Tell Duck-Vision to learn a new person
        
        Args:
            name: Name of the person to learn
            num_samples: Number of images to capture (3-10 recommended, default 5)
        """
        if self.vision_handler and self.connected:
            self.vision_handler.learn_person(name, num_samples)
            logger.info(f"Requested Duck-Vision to learn person: {name} with {num_samples} samples")
        else:
            logger.warning("Duck-Vision not connected, cannot learn person")
    
    def check_person(self, timeout: float = 3.0):
        """
        Tell Duck-Vision to check who is in front of the camera (synkron).
        Returns tuple: (found, name, confidence)
        """
        if self.vision_handler and self.connected:
            result = self.vision_handler.check_person(timeout=timeout)
            logger.info(f"Duck-Vision check_person result: {result}")
            return result
        else:
            logger.warning("Duck-Vision not connected, cannot check person")
            return (False, None, 0.0)
    
    def forget_person(self, name: str):
        """
        Tell Duck-Vision to forget a person
        
        Args:
            name: Name of the person to forget
        """
        if self.vision_handler and self.connected:
            self.vision_handler.forget_person(name)
            logger.info(f"Requested Duck-Vision to forget person: {name}")
        else:
            logger.warning("Duck-Vision not connected, cannot forget person")
    
    def list_known_people(self):
        """Tell Duck-Vision to list all known people"""
        if self.vision_handler and self.connected:
            self.vision_handler.list_known_people()
            logger.info("Requested list of known people from Duck-Vision")
        else:
            logger.warning("Duck-Vision not connected, cannot list people")
    
    def is_connected(self) -> bool:
        """Check if Duck-Vision service is connected"""
        if not self.vision_handler:
            return False
        
        # Use DuckVisionHandler's connected flag (set by MQTT on_connect callback)
        return self.vision_handler.connected
