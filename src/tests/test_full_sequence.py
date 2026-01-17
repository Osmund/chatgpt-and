#!/usr/bin/env python3
"""
Test full kommando-sekvens basert på OTA-svar
"""

import asyncio
from bleak import BleakClient

async def test_full_sequence(address):
    """Test komplett kommando-sekvens"""
    
    OTA_CHAR = "cafe8003-c0ff-ee01-8000-a110ca7ab1e0"
    CHAR1 = "cafe1001-c0ff-ee01-8000-a110ca7ab1e0"
    CHAR2 = "cafe1002-c0ff-ee01-8000-a110ca7ab1e0"
    
    print("🔐 Testing full command sequence...")
    
    try:
        async with BleakClient(address, timeout=20.0) as client:
            print("✅ Connected")
            await asyncio.sleep(2)
            
            # Subscribe to all notifications
            responses = {"ota": [], "char1": [], "char2": []}
            
            def ota_handler(sender, data):
                responses["ota"].append(data.hex())
                print(f"   🔔 OTA: {data.hex()}")
            
            def char1_handler(sender, data):
                responses["char1"].append(data.hex())
                print(f"   🔔 CHAR1: {data.hex()}")
            
            def char2_handler(sender, data):
                responses["char2"].append(data.hex())
                print(f"   🔔 CHAR2: {data.hex()}")
            
            await client.start_notify(OTA_CHAR, ota_handler)
            await client.start_notify(CHAR1, char1_handler)
            await client.start_notify(CHAR2, char2_handler)
            print("   📡 All notifications enabled\n")
            
            await asyncio.sleep(1)
            
            # Sekvens 1: Auth via OTA
            print("Step 1: OTA Auth")
            await client.write_gatt_char(OTA_CHAR, bytes([0x01, 0x00, 0x00, 0x00]), response=True)
            await asyncio.sleep(2)
            
            # Sekvens 2: Prøv forskjellige open-kommandoer på CHAR2 (ikke CHAR1)
            open_commands = [
                ("CHAR2 Open v1", CHAR2, bytes([0x00, 0x64, 0x00, 0x00, 0x00, 0x00])),
                ("CHAR2 Open v2", CHAR2, bytes([0x9a, 0x64])),
                ("CHAR2 Open v3", CHAR2, bytes([0x00, 0x64])),
                ("CHAR2 Move 100", CHAR2, bytes([0x01, 0x00, 0x64, 0x00])),
                ("CHAR1 Open v1", CHAR1, bytes([0x00, 0x64, 0x00, 0x00, 0x00, 0x00])),
                ("CHAR1 Move", CHAR1, bytes([0x01, 0x00, 0x64, 0x00])),
            ]
            
            for i, (name, char, cmd) in enumerate(open_commands, 2):
                print(f"\nStep {i}: {name} - {cmd.hex()}")
                try:
                    await client.write_gatt_char(char, cmd, response=True)
                    print("   ✅ Sent")
                    print("   👀 WATCH THE BLIND! (5 sec)")
                    await asyncio.sleep(5)
                    
                    if responses["char1"] or responses["char2"]:
                        print(f"   📬 Got response!")
                        responses["char1"].clear()
                        responses["char2"].clear()
                    
                except Exception as e:
                    print(f"   ❌ {e}")
                    break
            
            print("\n✅ Sequence complete")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    print("=" * 60)
    print("🦆 PowerView Full Sequence Test")
    print("=" * 60)
    print("\n👀 Watch TV blind carefully!\n")
    await asyncio.sleep(2)
    
    await test_full_sequence("D2:1D:6D:BB:C7:A2")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Stopped - note which command worked!")
