#!/usr/bin/env python3
"""
Stable connection test - prøver én kommando om gangen med stabil tilkobling
"""

import asyncio
from bleak import BleakClient

async def test_single_command(address, name, command_bytes, cmd_name):
    """Test én kommando med stabil tilkobling"""
    
    CHAR1 = "cafe1001-c0ff-ee01-8000-a110ca7ab1e0"
    CHAR2 = "cafe1002-c0ff-ee01-8000-a110ca7ab1e0"
    
    print(f"\n{'='*60}")
    print(f"Testing: {cmd_name}")
    print(f"Command: {command_bytes.hex()} ({len(command_bytes)} bytes)")
    print(f"{'='*60}")
    
    try:
        client = BleakClient(address, timeout=20.0)
        await client.connect()
        
        if not client.is_connected:
            print("❌ Could not connect")
            return False
        
        print("✅ Connected!")
        await asyncio.sleep(2)  # Wait for stable connection
        
        # Subscribe to notifications
        notification_received = False
        
        def notify_handler(sender, data):
            nonlocal notification_received
            notification_received = True
            print(f"   🔔 Response: {data.hex()}")
        
        try:
            await client.start_notify(CHAR1, notify_handler)
            print("   📡 Notifications enabled")
        except:
            print("   ⚠️  Could not enable notifications")
        
        await asyncio.sleep(1)
        
        # Send command WITH response
        print(f"   📤 Sending command (with response)...")
        try:
            await client.write_gatt_char(CHAR1, command_bytes, response=True)
            print(f"   ✅ Command sent successfully")
        except Exception as e:
            print(f"   ❌ Send error: {e}")
            await client.disconnect()
            return False
        
        # Wait for blind to move
        print(f"   ⏳ Waiting 8 seconds... (WATCH THE BLIND!)")
        for i in range(8):
            await asyncio.sleep(1)
            if notification_received:
                print(f"   📬 Got notification!")
        
        # Graceful disconnect
        print("   🔌 Disconnecting...")
        await client.disconnect()
        print("   ✅ Disconnected cleanly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        try:
            if client.is_connected:
                await client.disconnect()
        except:
            pass
        return False


async def main():
    print("=" * 60)
    print("🦆 Luxaflex Stable Protocol Test")
    print("=" * 60)
    
    address = "D2:1D:6D:BB:C7:A2"  # TV blind
    name = "TV"
    
    # Test commands one by one with stable connection
    test_commands = [
        ("Format 1: Open 100%", bytes([0x00, 0x64, 0x00, 0x00, 0x00, 0x00])),
        ("Format 2: Move to 100", bytes([0x9a, 0x64])),
        ("Format 3: Position 100", bytes([0x05, 0x64])),
        ("Format 4: Simple 100", bytes([0x64, 0x00])),
        ("Format 5: Byte 100", bytes([0x64])),
        ("Format 6: Open command", bytes([0x01, 0x64])),
        ("Format 7: Full packet", bytes([0x00, 0x00, 0x64, 0x00, 0x00, 0x00])),
    ]
    
    print(f"\nTesting {len(test_commands)} formats on {name} blind")
    print("👀 WATCH THE BLIND - if it moves, press Ctrl+C!\n")
    
    for i, (cmd_name, cmd_bytes) in enumerate(test_commands, 1):
        print(f"\n[Command {i}/{len(test_commands)}]")
        
        success = await test_single_command(address, name, cmd_bytes, cmd_name)
        
        if not success:
            print("⚠️  Skipping to next command...")
        
        # Pause between tests
        if i < len(test_commands):
            print("\n⏸️  Pausing 3 seconds before next test...")
            await asyncio.sleep(3)
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Test interrupted!")
        print("If the blind moved, note which format worked!")
