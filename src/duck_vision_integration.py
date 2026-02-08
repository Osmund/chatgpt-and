"""
Duck-Vision MQTT Handler for Anda/Samantha
Håndterer MQTT-kommunikasjon mellom Pi 4 (Anda) og Pi 5 (Duck-Vision kamera)
"""

import paho.mqtt.client as mqtt
import json
import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# MQTT QoS levels
QOS_FIRE_AND_FORGET = 0  # For status updates, object detections
QOS_AT_LEAST_ONCE = 1    # For commands that must arrive


class DuckVisionHandler:
    """
    Håndterer kommunikasjon med Duck-Vision på Pi 5.
    Brukes av Anda/Samantha for å motta ansikts- og objektdeteksjoner.
    
    Features:
    - Auto-reconnect ved nettverksproblemer
    - Last Will and Testament (LWT) for pålitelig status-deteksjon
    - threading.Event for effektiv synkron venting (ingen busy-wait)
    - QoS 1 for kommandoer som må leveres
    """
    
    # LWT topic - brokeren publiserer dette automatisk når klienten forsvinner
    from src.duck_config import DUCK_NAME as _DUCK_NAME
    STATUS_TOPIC = f"duck/{_DUCK_NAME.lower()}/status"
    
    # Reconnect settings
    RECONNECT_MIN_DELAY = 1    # sekunder
    RECONNECT_MAX_DELAY = 30   # sekunder
    
    def __init__(self, 
                 broker_host: str = "localhost",
                 broker_port: int = 1883,
                 on_face_detected: Optional[Callable] = None,
                 on_unknown_face: Optional[Callable] = None,
                 on_object_detected: Optional[Callable] = None,
                 on_learning_progress: Optional[Callable] = None,
                 on_speaker_recognized: Optional[Callable] = None,
                 on_voice_learned: Optional[Callable] = None):
        """
        Args:
            broker_host: MQTT broker adresse (default: localhost)
            broker_port: MQTT broker port (default: 1883)
            on_face_detected: Callback når kjent ansikt detekteres (name, confidence)
            on_unknown_face: Callback når ukjent ansikt detekteres
            on_object_detected: Callback når objekter detekteres (object_name, confidence)
            on_learning_progress: Callback under face learning (name, step, total, instruction)
            on_speaker_recognized: Callback når stemme gjenkjennes (name, confidence)
            on_voice_learned: Callback når stemmeprofil opprettet (name, success)
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # Callbacks
        self.on_face_detected = on_face_detected
        self.on_unknown_face = on_unknown_face
        self.on_object_detected = on_object_detected
        self.on_learning_progress = on_learning_progress
        self.on_speaker_recognized = on_speaker_recognized
        self.on_voice_learned = on_voice_learned
        
        # MQTT client setup
        self.client = mqtt.Client(client_id="samantha-vision-client")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Last Will and Testament - brokeren publiserer dette når vi forsvinner
        self.client.will_set(
            self.STATUS_TOPIC,
            payload=json.dumps({"status": "offline"}),
            qos=QOS_AT_LEAST_ONCE,
            retain=True
        )
        
        # Auto-reconnect settings
        self.client.reconnect_delay_set(
            min_delay=self.RECONNECT_MIN_DELAY,
            max_delay=self.RECONNECT_MAX_DELAY
        )
        
        self.connected = False
        self._intentional_disconnect = False
        self.pending_person_name = None
        
        # Pi 5 publisher status (tracked via duck/vision/status retained messages)
        self.publisher_online = False
        
        # Threading events for synkron venting (erstatter busy-wait polling)
        self._object_event = threading.Event()
        self._analysis_event = threading.Event()
        self._face_event = threading.Event()
        
        # Resultater (settes av callbacks, leses av synkrone metoder)
        self.last_object_seen = None
        self.last_object_confidence = 0.0
        self.last_all_objects = []
        self.last_openai_analysis = None
        self.last_face_result = None
    
    def connect(self):
        """Koble til MQTT broker"""
        try:
            self._intentional_disconnect = False
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info(f"Koblet til MQTT broker på {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            logger.error(f"Kunne ikke koble til MQTT: {e}")
            return False
    
    def disconnect(self):
        """Koble fra MQTT broker"""
        self._intentional_disconnect = True
        # Publiser offline-status før disconnect
        try:
            self.client.publish(
                self.STATUS_TOPIC,
                payload=json.dumps({"status": "offline"}),
                qos=QOS_AT_LEAST_ONCE,
                retain=True
            )
        except Exception:
            pass
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback når koblet til broker"""
        if rc == 0:
            self.connected = True
            # Subscribe til alle Duck-Vision events (QoS 1 for pålitelig levering)
            self.client.subscribe("duck/vision/#", qos=QOS_AT_LEAST_ONCE)
            # Subscribe til stemmegjenkjenning fra Duck-Vision
            self.client.subscribe("duck/audio/#", qos=QOS_AT_LEAST_ONCE)
            # Publiser online-status (retained slik at nye subscribere ser den)
            self.client.publish(
                self.STATUS_TOPIC,
                payload=json.dumps({"status": "online"}),
                qos=QOS_AT_LEAST_ONCE,
                retain=True
            )
            logger.info("MQTT tilkoblet, subscribed til duck/vision/#")
        else:
            logger.error(f"MQTT tilkobling feilet med rc={rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback når frakoblet broker - paho håndterer auto-reconnect"""
        self.connected = False
        if rc != 0 and not self._intentional_disconnect:
            logger.warning(f"MQTT uventet frakobling (rc={rc}), auto-reconnect aktiv...")
        else:
            logger.info("MQTT frakoblet")
    
    def _on_message(self, client, userdata, msg):
        """Callback når melding mottas"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == "duck/vision/status":
                self._handle_publisher_status(payload)
            elif topic == "duck/vision/face":
                self._handle_face_event(payload)
            elif topic == "duck/vision/object":
                self._handle_object_event(payload)
            elif topic in ("duck/vision/event", "duck/vision/events"):
                self._handle_generic_event(payload)
            elif topic == "duck/audio/speaker":
                self._handle_speaker_recognized(payload)
            elif topic == "duck/audio/voice_learned":
                self._handle_voice_learned(payload)
                
        except json.JSONDecodeError as e:
            logger.error(f"Ugyldig JSON fra {msg.topic}: {e}")
        except Exception as e:
            logger.error(f"Feil ved håndtering av MQTT-melding på {msg.topic}: {e}")
    
    def _handle_speaker_recognized(self, data: dict):
        """Håndter stemmegjenkjenning fra Duck-Vision"""
        name = data.get("name")
        confidence = data.get("confidence", 0.0)
        duration = data.get("speech_duration", 0.0)
        logger.info(f"🔊 Stemme gjenkjent: {name} ({confidence:.2%}, {duration:.1f}s tale)")
        if self.on_speaker_recognized:
            self.on_speaker_recognized(name, confidence)
    
    def _handle_voice_learned(self, data: dict):
        """Håndter at ny stemmeprofil er opprettet"""
        name = data.get("name")
        success = data.get("success", False)
        duration = data.get("speech_duration", 0.0)
        if success:
            logger.info(f"✅ Stemmeprofil opprettet for {name} ({duration:.1f}s tale)")
        else:
            logger.warning(f"❌ Kunne ikke opprette stemmeprofil for {name}")
        if self.on_voice_learned:
            self.on_voice_learned(name, success)
    
    def _handle_publisher_status(self, data: dict):
        """Håndter status fra Duck-Vision publisher på Pi 5 (retained LWT)"""
        status = data.get("status", "offline")
        was_online = self.publisher_online
        self.publisher_online = (status == "online")
        if self.publisher_online and not was_online:
            logger.info("Duck-Vision publisher er online (Pi 5 kamera tilgjengelig)")
        elif not self.publisher_online and was_online:
            logger.info("Duck-Vision publisher er offline (Pi 5 kamera ikke tilgjengelig)")
    
    def _handle_face_event(self, data: dict):
        """Håndter ansiktsdeteksjon (legacy - ikke brukt med on-demand)"""
        person_name = data.get("person_name")
        is_known = data.get("is_known", False)
        confidence = data.get("confidence", 0.0)
        
        if is_known and self.on_face_detected:
            self.on_face_detected(person_name, confidence)
        elif not is_known and self.on_unknown_face:
            self.on_unknown_face()
    
    def _handle_object_event(self, data: dict):
        """Håndter objektdeteksjon"""
        self.last_object_seen = data.get("object_name")
        self.last_object_confidence = data.get("confidence", 0.0)
        self.last_all_objects = data.get("all_objects", [])
        
        # Signal til ventende look_around()
        self._object_event.set()
        
        if self.on_object_detected:
            self.on_object_detected(self.last_object_seen, self.last_object_confidence)
    
    def _handle_generic_event(self, data: dict):
        """Håndter generiske events"""
        event_type = data.get("type") or data.get("event")
        
        if event_type == "person_learned":
            event_data = data.get("data", {})
            name = event_data.get("name")
            success = event_data.get("success", True)
            logger.info(f"Duck-Vision {'lærte' if success else 'kunne ikke lære'} {name}")
        
        elif event_type == "person_forgotten":
            name = data.get("data", {}).get("name")
            logger.info(f"Duck-Vision glemte {name}")
        
        elif event_type == "openai_analysis":
            data_content = data.get("data", {})
            self.last_openai_analysis = data_content.get("description")
            self._analysis_event.set()
            logger.debug(f"OpenAI Vision analyse mottatt: {len(self.last_openai_analysis or '')} tegn")
        
        elif event_type == "openai_analysis_error":
            self.last_openai_analysis = f"Feil: {data.get('error')}"
            self._analysis_event.set()
        
        elif event_type == "unknown_person":
            self.last_face_result = (False, None, 0.0)
            self._face_event.set()
            if self.on_unknown_face:
                self.on_unknown_face()
            logger.debug("Ukjent person detektert")
        
        elif event_type == "face_recognized":
            event_data = data.get("data", {})
            name = event_data.get("name")
            confidence = event_data.get("confidence", 0.0)
            self.last_face_result = (True, name, confidence)
            self._face_event.set()
            if self.on_face_detected:
                self.on_face_detected(name, confidence)
            logger.info(f"Gjenkjente {name} ({confidence:.2%})")
        
        elif event_type == "learning_progress":
            event_data = data.get("data", {})
            name = event_data.get("name")
            step = event_data.get("step")
            total = event_data.get("total")
            instruction = event_data.get("instruction")
            if self.on_learning_progress:
                self.on_learning_progress(name, step, total, instruction)
            logger.info(f"Learning progress: {step}/{total} - {instruction}")
        
        elif event_type == "check_person_result":
            event_data = data.get("data", {})
            found = event_data.get("found", False)
            if found:
                name = event_data.get("name")
                confidence = event_data.get("confidence", 0.0)
                self.last_face_result = (True, name, confidence)
                logger.info(f"check_person: Gjenkjente {name} ({confidence:.2%})")
            else:
                reason = event_data.get("reason", "unknown")
                logger.debug(f"Ingen person funnet: {reason}")
                self.last_face_result = (False, None, 0.0)
                if reason == "no_person_detected" and self.on_unknown_face:
                    self.on_unknown_face()
            self._face_event.set()
    
    # ── Kommandoer til Duck-Vision ──────────────────────────────
    
    def _publish_command(self, command: dict):
        """Publiser kommando til Duck-Vision med QoS 1"""
        if not self.connected:
            logger.warning("MQTT ikke tilkoblet, kan ikke sende kommando")
            return False
        if not self.publisher_online:
            logger.debug(f"Duck-Vision publisher offline, dropper kommando: {command.get('command')}")
            return False
        self.client.publish(
            f"duck/{self._DUCK_NAME.lower()}/commands",
            json.dumps(command),
            qos=QOS_AT_LEAST_ONCE
        )
        return True
    
    def request_object_detection(self):
        """Be Duck-Vision om å detektere objekter (async)"""
        self._publish_command({"command": "detect_object"})
    
    def look_around(self, timeout: float = 10.0) -> str:
        """
        Be Duck-Vision om å se seg rundt og vent på svar (synkron).
        Bruker threading.Event i stedet for busy-wait polling.
        
        Args:
            timeout: Maks tid å vente (sekunder)
        
        Returns:
            Beskrivelse av hva som ble sett
        """
        # Reset state og event
        self.last_object_seen = None
        self.last_object_confidence = 0.0
        self.last_all_objects = []
        self._object_event.clear()
        
        # Send kommando
        if not self._publish_command({"command": "detect_object"}):
            return "Duck-Vision er ikke tilkoblet"
        
        # Vent på svar - tråden sover helt til _object_event.set() kalles
        if not self._object_event.wait(timeout=timeout):
            return "Fikk ikke svar fra Duck-Vision (timeout)"
        
        # Bygg beskrivelse
        return self._format_object_description()
    
    def _format_object_description(self) -> str:
        """Formater objektdeteksjon til lesbar tekst"""
        if not self.last_object_seen:
            return "Jeg ser ingenting akkurat nå"
        
        if self.last_all_objects and len(self.last_all_objects) > 1:
            objects_desc = []
            for obj in self.last_all_objects:
                name = obj.get('name', 'ukjent')
                conf = obj.get('confidence', 0.0)
                objects_desc.append(f"{name} ({conf:.0%})" if conf > 0.7 else name)
            
            if len(objects_desc) == 1:
                return f"Jeg ser en {objects_desc[0]}"
            elif len(objects_desc) == 2:
                return f"Jeg ser en {objects_desc[0]} og en {objects_desc[1]}"
            else:
                last = objects_desc[-1]
                others = ", ".join([f"en {obj}" for obj in objects_desc[:-1]])
                return f"Jeg ser {others} og en {last}"
        else:
            obj = self.last_object_seen
            conf = self.last_object_confidence
            if conf > 0.7:
                return f"Jeg ser en {obj} ({conf:.0%} sikker)"
            else:
                return f"Jeg ser kanskje en {obj} ({conf:.0%})"
    
    def analyze_scene(self, question: Optional[str] = None, timeout: float = 15.0) -> str:
        """
        Be Duck-Vision om dyp scene-analyse med OpenAI Vision (synkron).
        
        Args:
            question: Spesifikt spørsmål (valgfritt)
            timeout: Maks tid å vente (sekunder)
        
        Returns:
            Detaljert beskrivelse fra OpenAI Vision
        """
        self.last_openai_analysis = None
        self._analysis_event.clear()
        
        command = {"command": "analyze_scene"}
        if question:
            command["question"] = question
        
        logger.info("Analyserer bildet med OpenAI Vision...")
        if not self._publish_command(command):
            return "Duck-Vision er ikke tilkoblet"
        
        if not self._analysis_event.wait(timeout=timeout):
            return "Fikk ikke svar fra OpenAI Vision (timeout)"
        
        result = self.last_openai_analysis
        self.last_openai_analysis = None
        return result or "Tomt svar fra OpenAI Vision"
    
    def check_person(self, timeout: float = 5.0):
        """
        Be Duck-Vision om å sjekke hvem som er foran kameraet (synkron).
        
        Returns:
            tuple: (found: bool, name: Optional[str], confidence: float)
        """
        self.last_face_result = None
        self._face_event.clear()
        
        if not self._publish_command({"command": "check_person"}):
            return (False, None, 0.0)
        
        if not self._face_event.wait(timeout=timeout):
            return (False, None, 0.0)
        
        result = self.last_face_result
        self.last_face_result = None
        return result or (False, None, 0.0)
    
    def learn_person(self, name: str, num_samples: int = 5):
        """Be Duck-Vision om å lære en ny person"""
        self._publish_command({
            "command": "learn_person",
            "name": name,
            "num_samples": num_samples
        })
        self.pending_person_name = name
        logger.info(f"Starter learning av {name} med {num_samples} bilder...")
    
    def forget_person(self, name: str):
        """Be Duck-Vision om å glemme en person (sletter også stemmeprofil)"""
        self._publish_command({"command": "forget_person", "name": name})
    
    def list_known_people(self):
        """Be Duck-Vision om liste over kjente personer"""
        self._publish_command({"command": "list_people"})
    
    def learn_voice(self, name: str, duration: float = 10.0):
        """Be Duck-Vision om å lære en persons stemme manuelt"""
        self._publish_command({
            "command": "learn_voice",
            "name": name,
            "duration": duration
        })
    
    def notify_speaking(self, speaking: bool):
        """Mute/unmute Duck-Vision mikrofon når anda snakker/er ferdig"""
        if not self.connected:
            return
        try:
            self.client.publish(
                f"duck/{self._DUCK_NAME.lower()}/speaking",
                json.dumps({"speaking": speaking}),
                qos=QOS_FIRE_AND_FORGET
            )
        except Exception as e:
            logger.debug(f"Kunne ikke sende speaking-status: {e}")

    def notify_conversation(self, active: bool):
        """Signal til Duck-Vision at en samtale er aktiv/avsluttet.
        
        Under samtale prioriterer Duck-Vision stemmegjenkjenning:
        - Senker cooldown (raskere matching)
        - Samler tale for bedre identifisering
        - Sender speaker_recognized event så fort match er funnet
        """
        if not self.connected:
            return
        try:
            self.client.publish(
                f"duck/{self._DUCK_NAME.lower()}/conversation",
                json.dumps({"active": active}),
                qos=QOS_FIRE_AND_FORGET
            )
            logger.info(f"{'💬 Samtale startet' if active else '💬 Samtale avsluttet'} (sendt til Duck-Vision)")
        except Exception as e:
            logger.debug(f"Kunne ikke sende conversation-status: {e}")

    def save_conversation_voice(self, name: str):
        """Be Duck-Vision om å lagre en stemmeprofil fra samtale-audio.
        
        Bruker audio som allerede er samlet under samtale-modus.
        MÅ kalles FØR notify_conversation(False), ellers er audioen slettet.
        """
        self._publish_command({
            "command": "save_conversation_voice",
            "name": name
        })
