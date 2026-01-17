#!/usr/bin/env python3
"""
Test OTA service (cafe8003) - kanskje autentisering kreves
"""

import asyncio
from bleak import BleakClient

async def test_ota_auth(address):
    """Prøv å autentisere via OTA service først"""
    
    OTA_SERVICE = "cafe8000-c0ff-ee01-8000-a110ca7ab1e0"
    OTA_CHAR = "cafe8003-c0ff-ee01-8000-a110ca7ab1e0"
    CONTROL_CHAR = "cafe1001-c0ff-ee01-8000-a110ca7ab1e0"
    
    print("🔐 Testing OTA authentication...")
    
    try:
        async with BleakClient(address, timeout=20.0) as client:
            print("✅ Connected")
            await asyncio.sleep(2)
            
            # Subscribe to OTA responses
            def ota_handler(sender, data):
                print(f"   🔔 OTA response: {data.hex()}")
            
            try:
                await client.start_notify(OTA_CHAR, ota_handler)
                print("   📡 OTA notifications enabled")
            except Exception as e:
                print(f"   ⚠️  OTA notify failed: {e}")
            
            await asyncio.sleep(1)
            
            # Prøv auth-kommandoer
            auth_commands = [
                ("Auth 1", bytes([0x01, 0x00, 0x00, 0x00])),
                ("Auth 2", bytes([0x00, 0x01])),
                ("Pairing", bytes([0xFF, 0x00])),
            ]
            
            for name, cmd in auth_commands:
                print(f"\n   Testing {name}: {cmd.hex()}")
                try:
                    await client.write_gatt_char(OTA_CHAR, cmd, response=True)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"   ❌ {e}")
            
            # Nå prøv å sende open-kommando
            print("\n📤 Sending OPEN command after auth attempt...")
            try:
                await client.write_gatt_char(CONTROL_CHAR, bytes([0x00, 0x64, 0x00, 0x00, 0x00, 0x00]), response=True)
                print("   ✅ Command sent")
                print("   👀 Watch the blind! (waiting 5 sec)")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"   ❌ {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    print("=" * 60)
    print("🦆 PowerView OTA Authentication Test")
    print("=" * 60)
    
    await test_ota_auth("D2:1D:6D:BB:C7:A2")  # TV blind


if __name__ == "__main__":
    asyncio.run(main())
