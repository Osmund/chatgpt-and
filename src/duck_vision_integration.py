"""
Duck-Vision MQTT Handler for Anda/Samantha
Integrer denne koden i chatgpt_voice.py på Pi 4 (oDuckberry-2)
"""

import paho.mqtt.client as mqtt
import json
import threading
import time
from typing import Optional, Callable

class DuckVisionHandler:
    """
    Håndterer kommunikasjon med Duck-Vision på Pi 5.
    Brukes av Anda/Samantha for å motta ansikts- og objektdeteksjoner.
    """
    
    def __init__(self, 
                 broker_host: str = "localhost",  # MQTT broker on Pi 4
                 broker_port: int = 1883,
                 on_face_detected: Optional[Callable] = None,
                 on_unknown_face: Optional[Callable] = None,
                 on_object_detected: Optional[Callable] = None,
                 on_learning_progress: Optional[Callable] = None):
        """
        Args:
            broker_host: MQTT broker adresse (default: "oDuckberry-vision.local")
            broker_port: MQTT broker port (vanligvis 1883)
            on_face_detected: Callback når kjent ansikt detekteres (name, confidence)
            on_unknown_face: Callback når ukjent ansikt detekteres
            on_object_detected: Callback når objekter detekteres (object_name, confidence)
            on_learning_progress: Callback under face learning (name, step, total, instruction)
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # Callbacks
        self.on_face_detected = on_face_detected
        self.on_unknown_face = on_unknown_face
        self.on_object_detected = on_object_detected
        self.on_learning_progress = on_learning_progress
        
        # MQTT client with fixed ID for status detection
        self.client = mqtt.Client(client_id="duck-vision")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        self.connected = False
        self.pending_person_name = None
        
        # For synkron look_around()
        self.last_object_seen = None
        self.last_object_confidence = 0.0
        self.last_all_objects = []
        
        # For OpenAI Vision analyse
        self.last_openai_analysis = None
        
        # For check_person synkron respons
        self.last_face_result = None
    
    def connect(self):
        """Koble til MQTT broker"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            print(f"✓ Koblet til MQTT broker på {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            print(f"❌ Kunne ikke koble til MQTT: {e}")
            return False
    
    def disconnect(self):
        """Koble fra MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback når koblet til broker"""
        if rc == 0:
            self.connected = True
            # Subscribe til alle Duck-Vision events
            self.client.subscribe("duck/vision/#")
            print("✓ Subscribed til duck/vision/#")
        else:
            print(f"❌ MQTT connection failed: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback når melding mottas"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "duck/vision/face":
                self._handle_face_event(payload)
            elif topic == "duck/vision/object":
                self._handle_object_event(payload)
            elif topic == "duck/vision/event" or topic == "duck/vision/events":
                self._handle_generic_event(payload)
                
        except Exception as e:
            print(f"❌ Error handling MQTT message: {e}")
    
    def _handle_face_event(self, data: dict):
        """Håndter ansiktsdeteksjon (legacy - ikke brukt med on-demand)"""
        person_name = data.get("person_name")
        is_known = data.get("is_known", False)
        confidence = data.get("confidence", 0.0)
        
        if is_known:
            # Kjent person
            if self.on_face_detected:
                self.on_face_detected(person_name, confidence)
        else:
            # Ukjent person
            if self.on_unknown_face:
                self.on_unknown_face()
    
    def _handle_object_event(self, data: dict):
        """Håndter objektdeteksjon"""
        object_name = data.get("object_name")
        confidence = data.get("confidence", 0.0)
        all_objects = data.get("all_objects", [])
        
        # Lagre for synkron look_around()
        self.last_object_seen = object_name
        self.last_object_confidence = confidence
        self.last_all_objects = all_objects
        
        # Callback
        if self.on_object_detected:
            self.on_object_detected(object_name, confidence)
    
    def _handle_generic_event(self, data: dict):
        """Håndter generiske events"""
        event_type = data.get("type") or data.get("event")  # Support both formats
        
        if event_type == "person_learned":
            event_data = data.get("data", {})
            name = event_data.get("name")
            success = event_data.get("success", True)
            if success:
                print(f"✓ Duck-Vision har lært {name}")
            else:
                print(f"❌ Kunne ikke lære {name}")
        
        elif event_type == "person_forgotten":
            event_data = data.get("data", {})
            name = event_data.get("name")
            print(f"✓ Duck-Vision har glemt {name}")
        
        elif event_type == "openai_analysis":
            # OpenAI Vision analyse fullført
            # Beskrivelsen er inne i 'data' objektet
            data_content = data.get("data", {})
            description = data_content.get("description")
            self.last_openai_analysis = description
            print(f"✓ Received OpenAI Vision analysis: {len(description) if description else 0} chars")
        
        elif event_type == "openai_analysis_error":
            # OpenAI Vision feilet
            error = data.get("error")
            self.last_openai_analysis = f"Feil: {error}"
        
        elif event_type == "unknown_person":
            # Ukjent person funnet ved check_person
            self.last_face_result = (False, None, 0.0)
            if self.on_unknown_face:
                self.on_unknown_face()
            print("👤 Ukjent person detektert")
        
        elif event_type == "face_recognized":
            # Kjent person funnet ved check_person
            event_data = data.get("data", {})
            name = event_data.get("name")
            confidence = event_data.get("confidence", 0.0)
            self.last_face_result = (True, name, confidence)
            if self.on_face_detected:
                self.on_face_detected(name, confidence)
            print(f"👋 Gjenkjente {name} ({confidence:.2%})")
        
        elif event_type == "learning_progress":
            # Real-time guidance under face learning
            event_data = data.get("data", {})
            name = event_data.get("name")
            step = event_data.get("step")
            total = event_data.get("total")
            instruction = event_data.get("instruction")
            if self.on_learning_progress:
                self.on_learning_progress(name, step, total, instruction)
            print(f"📸 Learning progress: {step}/{total} - {instruction}")
        
        elif event_type == "check_person_result":
            # Respons på check_person kommando
            event_data = data.get("data", {})
            found = event_data.get("found", False)
            if found:
                # Person funnet og gjenkjent
                name = event_data.get("name")
                confidence = event_data.get("confidence", 0.0)
                self.last_face_result = (True, name, confidence)
                print(f"👋 check_person: Gjenkjente {name} ({confidence:.2%})")
            else:
                # Ingen person funnet
                reason = event_data.get("reason", "unknown")
                print(f"👁️ Ingen person funnet: {reason}")
                self.last_face_result = (False, None, 0.0)
                # Trigger unknown face callback if no person detected
                if reason == "no_person_detected" and self.on_unknown_face:
                    self.on_unknown_face()
    
    # Kommandoer til Duck-Vision
    
    def request_object_detection(self):
        """Be Duck-Vision om å detektere objekter (async)"""
        command = {
            "command": "detect_object"
        }
        self.client.publish("duck/samantha/commands", json.dumps(command))
    
    def look_around(self, timeout: float = 10.0) -> str:
        """
        Be Duck-Vision om å se seg rundt og vent på svar (synkron).
        Returnerer beskrivelse av hva som ble sett.
        
        Args:
            timeout: Maks tid å vente (sekunder)
        
        Returns:
            String med beskrivelse, f.eks. "Jeg ser en person, en laptop og en mus"
        """
        self.last_object_seen = None
        self.last_object_confidence = 0.0
        self.last_all_objects = []
        
        # Send kommando
        self.request_object_detection()
        
        # Vent på svar
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.last_object_seen:
                # Lag en fin beskrivelse
                if self.last_all_objects and len(self.last_all_objects) > 1:
                    # Flere objekter - list dem
                    objects_desc = []
                    for obj in self.last_all_objects:
                        name = obj.get('name', 'ukjent')
                        conf = obj.get('confidence', 0.0)
                        # Legg til confidence hvis høy nok
                        if conf > 0.7:
                            objects_desc.append(f"{name} ({conf:.0%})")
                        else:
                            objects_desc.append(name)
                    
                    if len(objects_desc) == 1:
                        result = f"Jeg ser en {objects_desc[0]}"
                    elif len(objects_desc) == 2:
                        result = f"Jeg ser en {objects_desc[0]} og en {objects_desc[1]}"
                    else:
                        # 3 eller flere
                        last = objects_desc[-1]
                        others = ", ".join([f"en {obj}" for obj in objects_desc[:-1]])
                        result = f"Jeg ser {others} og en {last}"
                else:
                    # Bare ett objekt
                    obj = self.last_object_seen
                    conf = self.last_object_confidence
                    if conf > 0.7:
                        result = f"Jeg ser en {obj} ({conf:.0%} sikker)"
                    else:
                        result = f"Jeg ser kanskje en {obj} ({conf:.0%})"
                
                # Reset
                self.last_object_seen = None
                self.last_all_objects = []
                return result
            time.sleep(0.1)
        
        return "Jeg ser ingenting akkurat nå"
    
    def analyze_scene(self, question: Optional[str] = None, timeout: float = 15.0) -> str:
        """
        Be Duck-Vision om dyp scene-analyse med OpenAI Vision (synkron).
        
        Bruk denne når du trenger:
        - Detaljert beskrivelse av scene ("Hva skjer her?")
        - Farger, aktiviteter, stemninger
        - Tekst-gjenkjenning (OCR)
        - Komplekse spørsmål om bildet
        
        Args:
            question: Spesifikt spørsmål (valgfritt)
            timeout: Maks tid å vente (sekunder) - OpenAI tar vanligvis 2-5s
        
        Returns:
            Detaljert beskrivelse fra OpenAI Vision
        
        Examples:
            >>> vision.analyze_scene()
            "Bildet viser et stuerom med en person som sitter på en sofa..."
            
            >>> vision.analyze_scene("Hvilken farge har sofaen?")
            "Sofaen har en mørk grå farge med grønne puter."
            
            >>> vision.analyze_scene("Hva gjør personen?")
            "Personen sitter og holder en mobiltelefon, ser ut til å lese noe."
        """
        self.last_openai_analysis = None
        
        # Send kommando
        command = {
            "command": "analyze_scene"
        }
        if question:
            command["question"] = question
        
        print("📸 Analyserer bildet med OpenAI Vision, ett øyeblikk...")
        self.client.publish("duck/samantha/commands", json.dumps(command))
        
        # Vent på svar (OpenAI Vision tar lenger tid enn IMX500)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.last_openai_analysis:
                result = self.last_openai_analysis
                self.last_openai_analysis = None
                return result
            time.sleep(0.2)
        
        return "Fikk ikke svar fra OpenAI Vision (timeout)"
    
    def check_person(self, timeout: float = 5.0):
        """
        Be Duck-Vision om å sjekke hvem som er foran kameraet (synkron).
        Duck-Vision prøver opptil 3 ganger før den gir opp.
        Returnerer tuple: (found, name, confidence)
        """
        # Reset previous results
        self.last_face_result = None
        
        command = {
            "command": "check_person"
        }
        self.client.publish("duck/samantha/commands", json.dumps(command))
        
        # Wait for response (5s timeout for 3 attempts)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.last_face_result is not None:
                result = self.last_face_result
                self.last_face_result = None
                return result
            time.sleep(0.2)
        
        # Timeout - Duck-Vision svarte ikke
        return (False, None, 0.0)
    
    def learn_person(self, name: str, num_samples: int = 5):
        """Be Duck-Vision om å lære en ny person
        
        Args:
            name: Navn på personen
            num_samples: Antall bilder å ta (3-10 anbefalt, default 5)
        """
        command = {
            "command": "learn_person",
            "name": name,
            "num_samples": num_samples
        }
        self.client.publish("duck/samantha/commands", json.dumps(command))
        self.pending_person_name = name
        print(f"📸 Starter learning av {name} med {num_samples} bilder...")
    
    def forget_person(self, name: str):
        """Be Duck-Vision om å glemme en person"""
        command = {
            "command": "forget_person",
            "name": name
        }
        self.client.publish("duck/samantha/commands", json.dumps(command))
    
    def list_known_people(self):
        """Be Duck-Vision om liste over kjente personer"""
        command = {
            "command": "list_people"
        }
        self.client.publish("duck/samantha/commands", json.dumps(command))


# ═══════════════════════════════════════════════════════════════
# EKSEMPEL: Integrasjon i chatgpt_voice.py
# ═══════════════════════════════════════════════════════════════

class AndaWithVision:
    """
    Eksempel på hvordan Anda/Samantha kan bruke Duck-Vision.
    Legg denne koden inn i din eksisterende chatgpt_voice.py
    """
    
    def __init__(self, speak_func, listen_func):
        """
        Args:
            speak_func: Funksjon for TTS (f.eks. din existing speak())
            listen_func: Funksjon for STT (f.eks. din existing listen())
        """
        self.speak = speak_func
        self.listen = listen_func
        
        # Initialize Duck-Vision handler
        self.vision = DuckVisionHandler(
            on_face_detected=self.on_face_detected,
            on_unknown_face=self.on_unknown_face,
            on_object_detected=self.on_object_detected
        )
        
        self.waiting_for_name = False
        self.waiting_for_confirmation = False
        self.pending_person_name = None
    
    def start_vision(self):
        """Start Duck-Vision integrasjon"""
        if self.vision.connect():
            print("✓ Duck-Vision integrasjon aktiv!")
            return True
        return False
    
    def on_face_detected(self, name: str, confidence: float):
        """Callback når kjent ansikt detekteres"""
        greeting = self._get_greeting()
        self.speak(f"{greeting} {name}!")
        print(f"👋 Hilste på {name} (confidence: {confidence:.2%})")
    
    def on_unknown_face(self):
        """Callback når ukjent ansikt detekteres"""
        self.speak("Hei! Jeg ser deg, men jeg vet ikke hvem du er. Hvem er du?")
        self.waiting_for_name = True
        
        # Lytt etter svar
        response = self.listen()
        if response:
            name = self._extract_name_from_response(response)
            if name:
                self._ask_to_remember(name)
    
    def on_object_detected(self, object_name: str, confidence: float):
        """Callback når objekt detekteres"""
        self.speak(f"Jeg ser en {object_name}")
        print(f"👁️ Så {object_name} (confidence: {confidence:.2%})")
    
    def _ask_to_remember(self, name: str):
        """Spør om lov til å huske personen"""
        self.speak(f"Hei {name}! Får jeg lov å huske deg?")
        self.waiting_for_confirmation = True
        self.pending_person_name = name
        
        response = self.listen()
        if response and self._is_affirmative(response):
            # Send kommando til Duck-Vision
            self.vision.learn_person(name)
            self.speak("Supert! Se mot kameraet...")
            time.sleep(2)  # Gi tid til å ta bilde
            self.speak(f"Takk! Nå kjenner jeg deg, {name}!")
        else:
            self.speak("Ok, jeg husker deg ikke da.")
        
        self.waiting_for_confirmation = False
        self.pending_person_name = None
    
    def handle_what_do_you_see(self):
        """Håndter 'hva ser du?' spørsmål"""
        self.speak("La meg se...")
        self.vision.request_object_detection()
        # Objektdeteksjon callback vil bli kalt automatisk
    
    # Helper functions
    
    def _get_greeting(self) -> str:
        """Få passende hilsen basert på tid"""
        import datetime
        hour = datetime.datetime.now().hour
        if hour < 10:
            return "God morgen"
        elif hour < 18:
            return "Hei"
        else:
            return "God kveld"
    
    def _extract_name_from_response(self, text: str) -> Optional[str]:
        """Ekstraher navn fra respons"""
        text = text.lower()
        
        # Patterns: "jeg heter X", "jeg er X", "mitt navn er X", "X"
        patterns = [
            r"jeg heter (\w+)",
            r"jeg er (\w+)",
            r"mitt navn er (\w+)",
            r"navnet mitt er (\w+)",
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                return name.capitalize()
        
        # Hvis ingen pattern matcher, bruk første ord som er >3 bokstaver
        words = text.split()
        for word in words:
            word = word.strip('.,!?')
            if len(word) > 3 and word.isalpha():
                return word.capitalize()
        
        return None
    
    def _is_affirmative(self, text: str) -> bool:
        """Sjekk om respons er bekreftende"""
        text = text.lower()
        affirmative = ['ja', 'yes', 'ok', 'greit', 'gjerne', 'sure', 'yep', 'jepp']
        return any(word in text for word in affirmative)


# ═══════════════════════════════════════════════════════════════
# QUICK START GUIDE
# ═══════════════════════════════════════════════════════════════

"""
STEG 1: Installer MQTT broker på Pi 4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
sudo apt-get install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Test at det fungerer:
mosquitto_sub -t "duck/#" -v

STEG 2: Legg til i din eksisterende chatgpt_voice.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# I toppen av filen:
from duck_vision_integration import DuckVisionHandler

# I din main() eller init:
vision = DuckVisionHandler(
    on_face_detected=lambda name, conf: speak(f"Hei {name}!"),
    on_unknown_face=lambda: speak("Hei! Hvem er du?"),
    on_object_detected=lambda obj, conf: speak(f"Jeg ser en {obj}")
)
vision.connect()

# Når bruker spør "hva ser du?":
if "hva ser du" in user_input.lower():
    vision.request_object_detection()

STEG 3: Start systemene
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# På Pi 4 (Anda):
python3 chatgpt_voice.py

# På Pi 5 (Duck-Vision):
python3 duck_vision.py

STEG 4: Test!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Gå foran kamera på Pi 5
2. Anda skal si: "Hei! Hvem er du?"
3. Svar: "Jeg heter Magnus"
4. Anda: "Hei Magnus! Får jeg lov å huske deg?"
5. Svar: "Ja"
6. Se mot kameraet
7. Anda: "Takk! Nå kjenner jeg deg, Magnus!"
8. Test igjen - Anda skal nå si: "Hei Magnus!" direkte!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Så enkelt er det! 🦆⚡
"""
