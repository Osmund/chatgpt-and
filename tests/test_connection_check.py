#!/usr/bin/env python3
"""
Test is_connected() for Duck-Vision service
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from duck_services import get_services

services = get_services()
vision_service = services.get_vision_service()

print(f"vision_service exists: {vision_service is not None}")
print(f"vision_service.connected flag: {vision_service.connected}")
print(f"vision_service.vision_handler: {vision_service.vision_handler is not None}")

if vision_service.vision_handler:
    print(f"vision_handler.client exists: {hasattr(vision_service.vision_handler, 'client')}")
    if hasattr(vision_service.vision_handler, 'client'):
        client = vision_service.vision_handler.client
        print(f"client type: {type(client)}")
        print(f"client.is_connected() method exists: {hasattr(client, 'is_connected')}")
        if hasattr(client, 'is_connected'):
            try:
                result = client.is_connected()
                print(f"client.is_connected() returned: {result}")
            except Exception as e:
                print(f"client.is_connected() failed: {e}")

print(f"\nFinal result - vision_service.is_connected(): {vision_service.is_connected()}")
