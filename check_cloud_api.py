#!/usr/bin/env python3
"""
Sjekk om PowerView har cloud API
"""

import requests

# Hunter Douglas PowerView Cloud API endpoints (potensielle)
endpoints = [
    "https://api.hunterdouglas.com",
    "https://powerview.hunterdouglas.com",
    "https://cloud.powerview.hunterdouglas.com",
    "https://api.powerview.com",
]

print("🔍 Checking for PowerView Cloud API...\n")

for url in endpoints:
    try:
        print(f"Testing: {url}")
        response = requests.get(url, timeout=3)
        print(f"  Status: {response.status_code}")
        if response.status_code != 404:
            print(f"  ✅ Found endpoint!")
            print(f"  Response: {response.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"  ❌ {e}")
    print()

print("\n💡 PowerView Gen 3 ser ut til å kreve:")
print("   1. PowerView Gateway/Hub for lokal kontroll")
print("   2. Eller cloud API med autentisering")
print("\n📱 Siden appen fungerer uten WiFi, kan det være den bruker")
print("   Bluetooth-pairing som krever app-spesifikke keys/sertifikater")
