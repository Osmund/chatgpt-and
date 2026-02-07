#!/usr/bin/env python3
"""
Test Luxaflex gardin-kontroll
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.duck_tools import control_luxaflex_blinds


async def main():
    print("=" * 60)
    print("🧪 Test av Luxaflex gardin-kontroll")
    print("=" * 60)
    
    # Test 1: Åpne gardin ved TV
    print("\n📝 Test 1: Åpne gardin ved TV")
    result = await control_luxaflex_blinds("open", room="tv")
    print(result)
    
    print("\n⏳ Venter 3 sekunder...")
    await asyncio.sleep(3)
    
    # Test 2: Åpne gardin ved spisebord
    print("\n📝 Test 2: Åpne gardin ved spisebord")
    result = await control_luxaflex_blinds("open", room="spisebord")
    print(result)
    
    print("\n⏳ Venter 3 sekunder...")
    await asyncio.sleep(3)
    
    # Test 3: Åpne gardin ved trapp
    print("\n📝 Test 3: Åpne gardin ved trapp")
    result = await control_luxaflex_blinds("open", room="trapp")
    print(result)
    
    print("\n✅ Test fullført! Alle tre gardinene er åpnet.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Avbrutt av bruker")
        sys.exit(0)
