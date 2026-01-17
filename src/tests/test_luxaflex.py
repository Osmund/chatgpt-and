#!/usr/bin/env python3
"""
Test script for Luxaflex PowerView Gen3 Bluetooth integration
Brukes for å teste Bluetooth-kommunikasjon med Luxaflex gardiner
"""

import asyncio
from bleak import BleakScanner, BleakClient
import sys

# Kjente UUID-er for Luxaflex PowerView Gen3 (Hunter Douglas)
# Basert på reverse engineering fra community
POWERVIEW_SERVICE_UUID = "fe50"  # PowerView BLE Service
CONTROL_CHARACTERISTIC_UUID = "fe51"  # Command characteristic
STATUS_CHARACTERISTIC_UUID = "fe52"  # Status/response characteristic

# Kommando-bytes (må kanskje justeres basert på faktisk protokoll)
COMMAND_OPEN = bytes([0x01, 0x00, 0x00])  # Åpne helt
COMMAND_CLOSE = bytes([0x02, 0x00, 0x00])  # Lukke helt
COMMAND_STOP = bytes([0x03, 0x00, 0x00])  # Stopp
# Position: [0x04, position_high, position_low] der position er 0-65535


async def scan_for_blinds(timeout=10):
    """
    Scan etter Luxaflex/PowerView enheter i nærheten
    """
    print(f"🔍 Skanner etter Luxaflex PowerView enheter i {timeout} sekunder...")
    print("-" * 60)
    
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    
    powerview_devices = []
    
    for address, (device, adv_data) in devices.items():
        # Luxaflex/Hunter Douglas enheter har ofte "PowerView" i navnet
        # eller spesifikke manufacturer data
        if device.name and any(keyword in device.name.lower() for keyword in ['powerview', 'luxaflex', 'hunter', 'shade', 'blind']):
            powerview_devices.append(device)
            print(f"✅ Fant: {device.name}")
            print(f"   Adresse: {device.address}")
            print(f"   RSSI: {adv_data.rssi} dBm")
            if adv_data.manufacturer_data:
                print(f"   Manufacturer data: {adv_data.manufacturer_data}")
            if adv_data.service_uuids:
                print(f"   Service UUIDs: {adv_data.service_uuids}")
            print("-" * 60)
    
    # Finn DU1-enheter (Luxaflex gardiner)
    du1_devices = []
    print("\n📋 Søker etter DU1-enheter (Luxaflex gardiner):")
    print("=" * 80)
    
    for address, (device, adv_data) in devices.items():
        name = device.name if device.name else ""
        
        # DU1-enheter har navn som starter med "DU1:"
        if name.startswith("DU1:"):
            du1_devices.append(device)
            print(f"\n✅ Fant Luxaflex: {name}")
            print(f"   Adresse: {device.address}")
            print(f"   RSSI: {adv_data.rssi} dBm")
            
            if adv_data.manufacturer_data:
                print(f"   Manufacturer data:")
                for mfr_id, data in adv_data.manufacturer_data.items():
                    print(f"      ID {mfr_id} (0x{mfr_id:04x}): {data.hex()}")
            
            if adv_data.service_uuids:
                print(f"   Service UUIDs:")
                for uuid in adv_data.service_uuids:
                    print(f"      - {uuid}")
    
    print("\n" + "=" * 80)
    
    if not du1_devices:
        print("\n❌ Fant ingen DU1-enheter")
        
        # Vis alle enheter som backup
        print("\n📋 ALLE BLE-enheter:")
        for address, (device, adv_data) in devices.items():
            name = device.name if device.name else "<Ukjent>"
            print(f"  {name:40s} | {device.address} | {adv_data.rssi} dBm")
    
    return du1_devices


async def connect_and_discover(address):
    """
    Koble til en enhet og vis alle services/characteristics
    """
    print(f"\n🔗 Kobler til {address}...")
    
    try:
        async with BleakClient(address, timeout=15.0) as client:
            if not client.is_connected:
                print("❌ Kunne ikke koble til enheten")
                return False
            
            print("✅ Tilkoblet!")
            print("\n📡 Services og Characteristics:")
            print("=" * 60)
            
            for service in client.services:
                print(f"\n🔹 Service: {service.uuid}")
                print(f"   Beskrivelse: {service.description}")
                
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
                    
                    print(f"   └─ Characteristic: {char.uuid}")
                    print(f"      Properties: {', '.join(props)}")
                    
                    # Prøv å lese hvis readable
                    if 'read' in char.properties:
                        try:
                            value = await client.read_gatt_char(char.uuid)
                            print(f"      Value: {value.hex()} ({len(value)} bytes)")
                        except Exception as e:
                            print(f"      Value: Kunne ikke lese ({e})")
            
            print("\n" + "=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ Feil ved tilkobling: {e}")
        return False


async def test_control(address, command_uuid=None, command_data=None):
    """
    Test å sende en kommando til gardinen
    """
    if not command_uuid or not command_data:
        print("⚠️  Ingen kommando spesifisert, hopper over control test")
        return
    
    print(f"\n🎮 Tester kommando på {address}...")
    print(f"   UUID: {command_uuid}")
    print(f"   Data: {command_data.hex()}")
    
    try:
        async with BleakClient(address, timeout=15.0) as client:
            if not client.is_connected:
                print("❌ Kunne ikke koble til")
                return
            
            print("✅ Tilkoblet, sender kommando...")
            
            # Send kommando
            await client.write_gatt_char(command_uuid, command_data, response=True)
            print("✅ Kommando sendt!")
            
            # Vent litt og se om vi får status oppdatering
            await asyncio.sleep(2)
            
            print("✅ Test fullført")
            
    except Exception as e:
        print(f"❌ Feil ved sending av kommando: {e}")


async def main():
    print("=" * 60)
    print("🦆 Luxaflex PowerView Bluetooth Test")
    print("=" * 60)
    
    # Steg 1: Scan
    devices = await scan_for_blinds(timeout=10)
    
    if not devices:
        print("\n❌ Fant ingen PowerView-enheter")
        print("\n💡 Tips:")
        print("   - Sjekk at gardinene er skrudd på")
        print("   - Sørg for at Bluetooth er aktivert på gardinene")
        print("   - Prøv å stå nærmere gardinene")
        print("   - Se på 'Alle BLE-enheter' over - kanskje enheten")
        print("     har et annet navn enn forventet")
        return
    
    print(f"\n✅ Fant {len(devices)} PowerView-enhet(er)")
    
    # Steg 2: Koble til første enhet og vis info
    device = devices[0]
    print(f"\n📱 Velger: {device.name} ({device.address})")
    
    success = await connect_and_discover(device.address)
    
    if not success:
        print("\n❌ Kunne ikke koble til enheten")
        return
    
    # Steg 3: Spør brukeren om de vil teste en kommando
    print("\n" + "=" * 60)
    print("🎮 KOMMANDO TEST")
    print("=" * 60)
    print("\nVil du teste en kommando? (Dette kan få gardinen til å bevege seg!)")
    print("Kommandoer:")
    print("  1 - Åpne gardinen")
    print("  2 - Lukke gardinen")
    print("  3 - Stopp")
    print("  0 - Ikke test kommando")
    
    choice = input("\nVelg (0-3): ").strip()
    
    command_map = {
        '1': COMMAND_OPEN,
        '2': COMMAND_CLOSE,
        '3': COMMAND_STOP
    }
    
    if choice in command_map:
        print("\n⚠️  VIKTIG: Du må finne riktig UUID først!")
        print("Se på output over og identifiser hvilken characteristic")
        print("som har WRITE eller WRITE_NO_RESP property.")
        uuid = input("\nSkriv inn UUID for control characteristic (eller blank for å hoppe over): ").strip()
        
        if uuid:
            await test_control(device.address, uuid, command_map[choice])
        else:
            print("Hopper over kommando-test")
    else:
        print("Hopper over kommando-test")
    
    print("\n✅ Test fullført!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Avbrutt av bruker")
        sys.exit(0)
