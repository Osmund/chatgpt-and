#!/usr/bin/env python3
"""
Advanced Luxaflex protocol testing med read før write
"""

import asyncio
from bleak import BleakClient

async def discover_protocol(address, name):
    """Les først data fra gardinen, deretter test kommandoer"""
    
    print(f"\n{'='*80}")
    print(f"🔍 Discovering protocol for {name} ({address})")
    print(f"{'='*80}")
    
    CHAR1 = "cafe1001-c0ff-ee01-8000-a110ca7ab1e0"
    CHAR2 = "cafe1002-c0ff-ee01-8000-a110ca7ab1e0"
    
    try:
        async with BleakClient(address, timeout=20.0) as client:
            print("✅ Connected!")
            
            # Steg 1: Les nåværende tilstand
            print("\n📖 Reading current state...")
            
            try:
                data1 = await client.read_gatt_char(CHAR1)
                print(f"   cafe1001: {data1.hex()} (len={len(data1)})")
                if len(data1) > 0:
                    print(f"   Decoded: {list(data1)}")
            except Exception as e:
                print(f"   ❌ Cannot read cafe1001: {e}")
            
            try:
                data2 = await client.read_gatt_char(CHAR2)
                print(f"   cafe1002: {data2.hex()} (len={len(data2)})")
                if len(data2) > 0:
                    print(f"   Decoded: {list(data2)}")
            except Exception as e:
                print(f"   ❌ Cannot read cafe1002: {e}")
            
            # Steg 2: Enable notifications
            print("\n📡 Enabling notifications...")
            
            notifications_received = []
            
            def notification_handler(sender, data):
                msg = f"🔔 {sender.uuid}: {data.hex()}"
                print(f"   {msg}")
                notifications_received.append((sender.uuid, data))
            
            try:
                await client.start_notify(CHAR1, notification_handler)
                print("   ✅ Notifications on cafe1001")
            except:
                pass
            
            try:
                await client.start_notify(CHAR2, notification_handler)
                print("   ✅ Notifications on cafe1002")
            except:
                pass
            
            await asyncio.sleep(1)
            
            # Steg 3: Test progressive kommandoer
            test_commands = [
                # Based on potential protocols
                ("Open 100% v1", bytes([0x00, 0x64, 0x00, 0x00, 0x00, 0x00])),
                ("Open 100% v2", bytes([0x9a, 0x64])),
                ("Open 100% v3", bytes([0x05, 0x64])),
                ("Move Open", bytes([0x00, 0x00, 0x64, 0x00])),
                ("Position 100", bytes([0x64, 0x00])),
                ("Simple Open", bytes([0x01])),
            ]
            
            print(f"\n🧪 Testing {len(test_commands)} command formats...")
            print("👀 WATCH THE BLIND! Press Ctrl+C when it moves!\n")
            
            for i, (name, cmd) in enumerate(test_commands, 1):
                print(f"\n[{i}/{len(test_commands)}] {name}: {cmd.hex()}")
                
                try:
                    await client.write_gatt_char(CHAR1, cmd, response=False)
                    print(f"   📤 Sent to cafe1001")
                    
                    # Wait and check for notifications
                    await asyncio.sleep(5)
                    
                    if notifications_received:
                        print(f"   📬 Received {len(notifications_received)} notifications")
                        notifications_received.clear()
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
            
            print("\n✅ Test completed")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")


async def main():
    print("=" * 80)
    print("🦆 Luxaflex Protocol Discovery v2")
    print("=" * 80)
    print("\nTesting TV blind (best signal)")
    print("⚠️  Starting in 3 seconds...\n")
    await asyncio.sleep(3)
    
    await discover_protocol("D2:1D:6D:BB:C7:A2", "TV")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Test stopped!")
        print("If the blind moved, note which command format worked")
