#!/usr/bin/env python3
"""
Debug is_connected() status
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from duck_services import get_services

services = get_services()
vision_service = services.get_vision_service()

print(f"vision_service exists: {vision_service is not None}")

if vision_service:
    print(f"vision_handler exists: {vision_service.vision_handler is not None}")
    
    if vision_service.vision_handler:
        handler = vision_service.vision_handler
        print(f"handler.connected flag: {handler.connected}")
        print(f"handler.client exists: {handler.client is not None}")
        
        # Wait a bit for async connection
        print("\nWaiting 2 seconds for MQTT connection...")
        time.sleep(2)
        print(f"handler.connected after wait: {handler.connected}")
    
    print(f"\nFinal: vision_service.is_connected() = {vision_service.is_connected()}")
