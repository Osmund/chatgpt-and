#!/usr/bin/env python3
"""
Test script for Duck-Vision service
Starter servicen manuelt for å teste MQTT-tilkobling
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from duck_vision_service import DuckVisionService

def main():
    print("🦆 Testing Duck-Vision Service...")
    print("-" * 50)
    
    # Opprett service
    vision_service = DuckVisionService(broker_host="localhost")
    print(f"✅ DuckVisionService opprettet")
    
    # Prøv å starte
    print("\n📡 Prøver å koble til MQTT broker...")
    connected = vision_service.start()
    
    if connected:
        print("✅ Duck-Vision service startet!")
        print(f"   Tilkoblet: {vision_service.is_connected()}")
        print("\n💡 Service kjører. Trykk Ctrl+C for å stoppe...")
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopper service...")
            vision_service.stop()
            print("✅ Service stoppet")
    else:
        print("❌ Duck-Vision service kunne ikke starte")
        print("   Sjekk at MQTT broker (mosquitto) kjører:")
        print("   sudo systemctl status mosquitto")

if __name__ == "__main__":
    main()
