#!/usr/bin/env python3
"""
Test Samsung TV og Panasonic AC via Bluetooth
"""

import asyncio
from bleak import BleakClient, BleakScanner

# Enheter fra scan
SAMSUNG_TV = {
    "name": "Samsung 8 Series (65)",
    "address": "00:C3:F4:73:96:F9",
    "manufacturer_id": 117
}

PANASONIC_AC = {
    "name": "Aircondition",
    "address": "D7:FF:7A:3D:AA:55",
    "service_uuid": "0000fe0f-0000-1000-8000-00805f9b34fb"
}


async def discover_device(address, name):
    """Finn alle services og characteristics for en enhet"""
    
    print(f"\n{'='*80}")
    print(f"🔍 Discovering: {name}")
    print(f"   Address: {address}")
    print(f"{'='*80}")
    
    try:
        async with BleakClient(address, timeout=20.0) as client:
            print("✅ Connected!")
            await asyncio.sleep(2)
            
            print("\n📡 Services and Characteristics:")
            print("-" * 80)
            
            for service in client.services:
                print(f"\n🔹 Service: {service.uuid}")
                print(f"   Description: {service.description}")
                
                for char in service.characteristics:
                    props = []
                    if 'read' in char.properties:
                        props.append('READ')
                    if 'write' in char.properties:
                        props.append('WRITE')
                    if 'write-without-response' in char.properties:
                        props.append('WRITE_NO_RESP')
                    if 'notify' in char.properties:
                        props.append('NOTIFY')
                    if 'indicate' in char.properties:
                        props.append('INDICATE')
                    
                    print(f"\n   📝 Characteristic: {char.uuid}")
                    print(f"      Description: {char.description}")
                    print(f"      Properties: {', '.join(props)}")
                    
                    # Try to read if readable
                    if 'read' in char.properties:
                        try:
                            value = await client.read_gatt_char(char.uuid)
                            print(f"      Value: {value.hex()} ({len(value)} bytes)")
                            # Try to decode as string
                            try:
                                text = value.decode('utf-8', errors='ignore')
                                if text.isprintable():
                                    print(f"      Text: {text}")
                            except:
                                pass
                        except Exception as e:
                            print(f"      Read error: {e}")
            
            print("\n" + "-" * 80)
            return True
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


async def test_samsung_tv():
    """Test Samsung TV"""
    print("\n" + "="*80)
    print("📺 SAMSUNG TV TEST")
    print("="*80)
    
    success = await discover_device(SAMSUNG_TV["address"], SAMSUNG_TV["name"])
    
    if success:
        print("\n💡 Samsung TV info:")
        print("   - Mange Samsung TVs bruker proprietary BLE for remote control")
        print("   - Kan kreve pairing via SmartThings app")
        print("   - Alternativt: Bruk Samsung TV REST API via WiFi/LAN")


async def test_panasonic_ac():
    """Test Panasonic AC"""
    print("\n" + "="*80)
    print("❄️ PANASONIC AC TEST")
    print("="*80)
    
    success = await discover_device(PANASONIC_AC["address"], PANASONIC_AC["name"])
    
    if success:
        print("\n💡 Panasonic AC info:")
        print("   - Service UUID: 0000fe0f (vendor specific)")
        print("   - Kan være Panasonic Comfort Cloud protokoll")
        print("   - Eller lokal IR-bridge med BLE control")


async def main():
    print("=" * 80)
    print("🦆 BLE Device Discovery")
    print("=" * 80)
    print("\nTesting Samsung TV and Panasonic AC\n")
    
    # Test 1: Samsung TV
    await test_samsung_tv()
    
    await asyncio.sleep(3)
    
    # Test 2: Panasonic AC
    await test_panasonic_ac()
    
    print("\n" + "="*80)
    print("✅ Discovery complete!")
    print("="*80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
