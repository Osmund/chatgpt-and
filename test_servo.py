#!/usr/bin/env python3
"""
Test-script for å verifisere PCA9685 servo-kontroll
Kjør dette ETTER at PCA9685 er koblet til:
- VCC → 3.3V (pin 1)
- GND → Ground (pin 6)
- SDA → GPIO 2 (pin 3)
- SCL → GPIO 3 (pin 5)
- V+ → Ekstern 5V strøm
- Servo på kanal 0
"""

import time
from duck_beak import Beak, SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG

def test_basic_movement():
    """Test grunnleggende servo-bevegelse"""
    print("=== Test 1: Grunnleggende bevegelse ===")
    print(f"Initialiserer servo på PCA9685 kanal {SERVO_CHANNEL}...")
    
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        
        print("\n1. Lukket posisjon (0%)")
        beak.open_pct(0.0)
        time.sleep(2)
        
        print("2. 25% åpen")
        beak.open_pct(0.25)
        time.sleep(2)
        
        print("3. 50% åpen")
        beak.open_pct(0.5)
        time.sleep(2)
        
        print("4. 75% åpen")
        beak.open_pct(0.75)
        time.sleep(2)
        
        print("5. Fullt åpen (100%)")
        beak.open_pct(1.0)
        time.sleep(2)
        
        print("6. Lukker smootht...")
        beak.close()
        time.sleep(1)
        
        print("\n✅ Test 1 fullført!")
        beak.stop()
        return True
        
    except Exception as e:
        print(f"\n❌ Test 1 feilet: {e}")
        return False

def test_smooth_movement():
    """Test smooth bevegelse"""
    print("\n=== Test 2: Smooth bevegelse ===")
    
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        
        print("Åpner smootht...")
        beak.goto_deg_smooth(OPEN_DEG, step_deg=3, dt=0.02)
        time.sleep(1)
        
        print("Lukker smootht...")
        beak.goto_deg_smooth(CLOSE_DEG, step_deg=3, dt=0.02)
        time.sleep(1)
        
        print("\n✅ Test 2 fullført!")
        beak.stop()
        return True
        
    except Exception as e:
        print(f"\n❌ Test 2 feilet: {e}")
        return False

def test_rapid_movement():
    """Test rask på/av bevegelse (snakking)"""
    print("\n=== Test 3: Rask bevegelse (snakking) ===")
    
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        
        print("Simulerer snakking i 5 sekunder...")
        from duck_beak import snakk_syklus
        snakk_syklus(beak, 5000)
        
        print("\n✅ Test 3 fullført!")
        beak.stop()
        return True
        
    except Exception as e:
        print(f"\n❌ Test 3 feilet: {e}")
        return False

def main():
    print("=" * 50)
    print("PCA9685 Servo Test")
    print("=" * 50)
    print("\nSjekk at:")
    print("1. PCA9685 er koblet til I2C (SDA=GPIO2, SCL=GPIO3)")
    print("2. PCA9685 VCC er koblet til 3.3V")
    print("3. PCA9685 V+ er koblet til ekstern 5V strøm")
    print("4. Servo er koblet til kanal 0 på PCA9685")
    print("5. Alle grounds er koblet sammen")
    print("\nTrykk Enter for å starte test...")
    input()
    
    results = []
    results.append(("Grunnleggende bevegelse", test_basic_movement()))
    
    print("\nTrykk Enter for neste test...")
    input()
    results.append(("Smooth bevegelse", test_smooth_movement()))
    
    print("\nTrykk Enter for neste test...")
    input()
    results.append(("Rask bevegelse", test_rapid_movement()))
    
    print("\n" + "=" * 50)
    print("TESTRESULTATER")
    print("=" * 50)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FEIL"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n🎉 Alle tester bestått! PCA9685 fungerer perfekt.")
    else:
        print("\n⚠️  Noen tester feilet. Sjekk tilkoblingene.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest avbrutt av bruker")
    except Exception as e:
        print(f"\n\nUventet feil: {e}")
        print("\nTroubleshooting:")
        print("- Sjekk at I2C er aktivert: ls /dev/i2c*")
        print("- Sjekk at PCA9685 er synlig: i2cdetect -y 1")
        print("- Sjekk at Python-biblioteket er installert: pip list | grep pca9685")
