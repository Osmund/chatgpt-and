#!/usr/bin/env python3
"""
Test Panasonic AC kontroll via Bluetooth
"""

import asyncio
from bleak import BleakClient

PANASONIC_AC = "D7:FF:7A:3D:AA:55"

# Interessante characteristics fra discovery
SERVICE_UUID = "0000fe0f-0000-1000-8000-00805f9b34fb"
MAIN_CHAR = "97fe6561-1001-4f62-86e9-b71ee2da3d22"  # READ, WRITE, NOTIFY
CONTROL_CHAR = "97fe6561-2001-4f62-86e9-b71ee2da3d22"  # READ, WRITE


async def test_ac_control():
    """Test Panasonic AC kommandoer"""
    
    print("=" * 80)
    print("❄️ Panasonic AC Control Test")
    print("=" * 80)
    
    try:
        client = BleakClient(PANASONIC_AC, timeout=20.0)
        await client.connect()
        
        if not client.is_connected:
            print("❌ Could not connect")
            return
        
        print("✅ Connected to AC")
        await asyncio.sleep(3)  # Wait for stable connection
        
        # Subscribe to notifications
        notifications = []
        
        def notification_handler(sender, data):
            notifications.append(data)
            print(f"   🔔 Notification: {data.hex()} (len={len(data)})")
            if len(data) > 0:
                print(f"      Bytes: {list(data)}")
        
        try:
            await client.start_notify(MAIN_CHAR, notification_handler)
            print("📡 Notifications enabled on main characteristic\n")
        except Exception as e:
            print(f"⚠️  Notifications: {e}\n")
        
        await asyncio.sleep(2)
        
        # Step 1: Read current state
        print("Step 1: Reading current state...")
        try:
            current = await client.read_gatt_char(MAIN_CHAR)
            print(f"   Current state: {current.hex()} (len={len(current)})")
            print(f"   Bytes: {list(current)}\n")
        except Exception as e:
            print(f"   ⚠️  Read: {e}\n")
        
        await asyncio.sleep(1)
        
        # Step 2: Test commands one by one
        test_commands = [
            ("Power ON v1", bytes([0x01])),
            ("Power ON v2", bytes([0x01, 0x00])),
            ("Power ON v3", bytes([0x01, 0x01, 0x18])),
            ("Temp 22°C", bytes([0x16])),
            ("Temp 24°C", bytes([0x18])),
            ("Cool mode", bytes([0x02, 0x18])),
            ("Power OFF", bytes([0x00])),
        ]
        
        for i, (name, cmd) in enumerate(test_commands, 2):
            print(f"Step {i}: Testing {name}")
            print(f"   Command: {cmd.hex()} (len={len(cmd)})")
            
            try:
                await client.write_gatt_char(MAIN_CHAR, cmd, response=True)
                print(f"   ✅ Sent")
                
                print(f"   ⏳ Waiting 4 seconds... (🎧 listen for beep!)")
                await asyncio.sleep(4)
                
                if notifications:
                    print(f"   📬 Received {len(notifications)} notifications")
                    notifications.clear()
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print()
            await asyncio.sleep(1)
        
        # Clean disconnect
        print("🔌 Disconnecting...")
        await client.disconnect()
        print("✅ Test complete!")
        
    except Exception as e:
        print(f"❌ Connection error: {e}")


async def main():
    print("\n⚠️  Make sure AC is powered on and in range!")
    print("🎧 Listen for beep sounds from AC")
    print("👀 Watch for LED changes on AC\n")
    
    await asyncio.sleep(2)
    
    await test_ac_control()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Test stopped!")
        print("If AC responded (beep/LED), note which command worked!")
