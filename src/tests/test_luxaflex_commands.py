#!/usr/bin/env python3
"""
Debug script for å finne riktig Luxaflex protokoll
"""

import asyncio
from bleak import BleakClient

# Test forskjellige kommando-formater
TEST_COMMANDS = {
    "Format 1 - Simple open": bytes([0x01, 0x64, 0x00]),  # 0x64 = 100%
    "Format 2 - Open command": bytes([0x00, 0x64]),
    "Format 3 - Full open": bytes([0x00, 0x00, 0x00, 0x64]),
    "Format 4 - Move to 100": bytes([0x9A, 0x64, 0x00, 0x00]),
    "Format 5 - Position 100": bytes([0x05, 0x00, 0x64, 0x00]),
    "Format 6 - ASCII command": b"OPEN\x00",
    "Format 7 - Hex open": bytes([0xFF, 0x00, 0x64]),
    "Format 8 - Simple 0x64": bytes([0x64]),
}

async def test_shade_commands(address, shade_name):
    """Test forskjellige kommando-formater på en gardin"""
    
    print(f"\n{'='*80}")
    print(f"🧪 Testing commands for {shade_name} ({address})")
    print(f"{'='*80}")
    
    SERVICE_UUID = "0000fdc1-0000-1000-8000-00805f9b34fb"
    CHAR1 = "cafe1001-c0ff-ee01-8000-a110ca7ab1e0"
    CHAR2 = "cafe1002-c0ff-ee01-8000-a110ca7ab1e0"
    
    for cmd_name, cmd_bytes in TEST_COMMANDS.items():
        print(f"\n📝 Testing: {cmd_name}")
        print(f"   Data: {cmd_bytes.hex()} ({len(cmd_bytes)} bytes)")
        
        # New connection for each test
        try:
            async with BleakClient(address, timeout=20.0) as client:
                if not client.is_connected:
                    print("   ❌ Could not connect")
                    continue
                
                print("   ✅ Connected")
                
                # Try on CHAR1
                print(f"   📤 Sending to cafe1001...")
                try:
                    await client.write_gatt_char(CHAR1, cmd_bytes, response=False)
                    print(f"      ✅ Sent")
                    await asyncio.sleep(3)  # Wait to see if blind moves
                except Exception as e:
                    print(f"      ❌ Error: {e}")
                
                print(f"   ⏸️  Did the blind move? (waiting 5 sec)")
                await asyncio.sleep(5)
                
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
            continue


async def main():
    print("=" * 80)
    print("🦆 Luxaflex Protocol Discovery")
    print("=" * 80)
    print("\nThis will test different command formats on the TV blind.")
    print("Watch the blind and press Ctrl+C when you see it move!")
    print("\n⚠️  Starting in 3 seconds...")
    await asyncio.sleep(3)
    
    # Test på TV-gardinen (best signal)
    await test_shade_commands("D2:1D:6D:BB:C7:A2", "TV")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Stopped by user - Note which command worked!")
        print("Update the command format in duck_tools.py")
