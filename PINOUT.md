# ChatGPT Duck - Komplett Pinout Diagram

## Raspberry Pi 5 GPIO Header (40-pin)

```
    3.3V  (1) (2)  5V     ← PCA9685 VCC (3.3V) + MAX98357A VIN (5V)
   GPIO2  (3) (4)  5V     ← PCA9685 SDA (I2C)
   GPIO3  (5) (6)  GND    ← GND (felles for alle komponenter)
   GPIO4  (7) (8)  GPIO14
     GND  (9) (10) GPIO15
  GPIO17 (11) (12) GPIO18 ← MAX98357A BCLK (I2S Bit Clock)
  GPIO27 (13) (14) GND
  GPIO22 (15) (16) GPIO23
    3.3V (17) (18) GPIO24
  GPIO10 (19) (20) GND
   GPIO9 (21) (22) GPIO25
  GPIO11 (23) (24) GPIO8
     GND (25) (26) GPIO7
   GPIO0 (27) (28) GPIO1
   GPIO5 (29) (30) GND
   GPIO6 (31) (32) GPIO12
  GPIO13 (33) (34) GND
  GPIO19 (35) (36) GPIO16 ← MAX98357A LRCK (I2S Word Select)
  GPIO26 (37) (38) GPIO20
     GND (39) (40) GPIO21 ← MAX98357A DIN (I2S Data)
```

---

## Komponentoversikt

### 1. PCA9685 (16-Channel PWM Servo Driver)
Styrer servo for nebb-bevegelse via I2C.

| PCA9685 Pin | →  | Raspberry Pi 5 Pin | GPIO | Beskrivelse |
|-------------|----|--------------------|------|-------------|
| VCC         | →  | Pin 1 eller 17     | 3.3V | Logikk-strøm |
| GND         | →  | Pin 6, 9, 14, etc  | GND  | Ground |
| SDA         | →  | Pin 3              | GPIO2 | I2C Data |
| SCL         | →  | Pin 5              | GPIO3 | I2C Clock |
| V+          | →  | **Ekstern 5V**     | -    | Servo strøm (VIKTIG: Bruk separat strømforsyning!) |
| Servo CH0   | →  | Servo signal       | -    | Nebb-servo på kanal 0 |

**⚠️ VIKTIG:** PCA9685 V+ skal kobles til en **separat 5V strømforsyning** (f.eks. battery pack eller USB power bank), IKKE til Raspberry Pi 5V! Dette forhindrer at Pi'en rebootes når servoen trekker mye strøm.

---

### 2. MAX98357A (I2S Class-D Audio Amplifier)
Forsterker for høyttaler via I2S digital audio.

| MAX98357A Pin | →  | Raspberry Pi 5 Pin | GPIO | Beskrivelse |
|---------------|----|--------------------|------|-------------|
| VIN (eller VDD) | → | Pin 2 eller 4    | 5V   | Strøm (kan også bruke 3.3V avhengig av modul) |
| GND           | →  | Pin 6, 9, 14, etc  | GND  | Ground |
| DIN           | →  | Pin 40             | GPIO21 | I2S Data (PCM_DOUT) |
| BCLK          | →  | Pin 12             | GPIO18 | I2S Bit Clock (PCM_CLK) |
| LRCK (WS)     | →  | Pin 35             | GPIO19 | I2S Word Select / Left-Right Clock (PCM_FS) |
| SD (Shutdown) | →  | Pin 1 eller 17     | 3.3V | Shutdown control - kobles til 3.3V for "alltid på" |
| GAIN          | →  | Pin 6, 9, 14, etc  | GND  | Gain control - GND = 9dB (lavere forsterkning, mindre pop) |
| SPK+          | →  | Høyttaler +        | -    | Speaker positive |
| SPK-          | →  | Høyttaler -        | -    | Speaker negative |

**Notater:**
- **SD pin:** Kobles til fast 3.3V for kontinuerlig drift. Alternativt til GND hvis du vil ha forsterkeren av som standard.
- **GAIN pin:** 
  - Flytende eller til VIN = 15dB forsterkning (høyere volum, mer pop)
  - Til GND = 9dB forsterkning (lavere volum, mindre pop) ← **Anbefalt**

---

### 3. RGB LED (Monk Makes eller lignende)
Status-indikator med rød, grønn og blå LED.

| RGB LED Pin | →  | Raspberry Pi 5 Pin | GPIO | Beskrivelse |
|-------------|----|--------------------|------|-------------|
| R (Rød)     | →  | Pin 11             | GPIO17 | Rød LED kontroll |
| G (Grønn)   | →  | Pin 13             | GPIO27 | Grønn LED kontroll |
| B (Blå)     | →  | Pin 15             | GPIO22 | Blå LED kontroll |
| GND         | →  | Pin 6, 9, 14, etc  | GND  | Ground (felles cathode) |

---

### 4. USB Mikrofon (USB PnP Sound Device)
Plug & play - ingen GPIO brukt.

| Mikrofon | →  | Raspberry Pi 5 |
|----------|----|--------------------|
| USB kabel | → | USB port (hvilken som helst) |

---

## Fullstendig Tilkoblingstabel

### Raspberry Pi 5 GPIO Bruk

| Pin # | GPIO  | Funksjon | Komponent | Notat |
|-------|-------|----------|-----------|-------|
| 1     | 3.3V  | Strøm    | PCA9685 VCC + MAX98357A SD | Logikk-strøm |
| 2     | 5V    | Strøm    | MAX98357A VIN | Alternativt pin 4 |
| 3     | GPIO2 | I2C SDA  | PCA9685 SDA | Servo kontroll |
| 5     | GPIO3 | I2C SCL  | PCA9685 SCL | Servo kontroll |
| 6     | GND   | Ground   | Alle komponenter | Felles ground |
| 11    | GPIO17| Digital Out | RGB LED Rød | Status-indikator |
| 12    | GPIO18| I2S BCLK | MAX98357A BCLK | Audio bit clock |
| 13    | GPIO27| Digital Out | RGB LED Grønn | Status-indikator |
| 15    | GPIO22| Digital Out | RGB LED Blå | Status-indikator |
| 35    | GPIO19| I2S LRCK | MAX98357A LRCK | Audio word select |
| 40    | GPIO21| I2S DIN  | MAX98357A DIN | Audio data |

### Totalt GPIO-bruk
- **I2C:** 2 pins (GPIO2, GPIO3) - PCA9685 servo driver
- **I2S:** 3 pins (GPIO18, GPIO19, GPIO21) - MAX98357A audio
- **RGB LED:** 3 pins (GPIO17, GPIO27, GPIO22) - Status-indikatorer
- **Totalt:** 8 GPIO pins brukt

---

## Strømforsyning

### Raspberry Pi 5
- **Krav:** 5V/5A USB-C strømforsyning (offisiell anbefalt)
- **Forbruker:**
  - Pi 5: ~3-5W (idle til full load)
  - PCA9685 logikk: ~10mA @ 3.3V
  - MAX98357A: ~1-2W @ max volum
  - RGB LED: ~60mA (20mA per farge)

### PCA9685 Servo Strøm (V+)
- **⚠️ KRITISK:** Bruk **separat 5V strømforsyning**
- **Eksempler:**
  - USB power bank (5V 2A+)
  - 4x AA batterier (6V via regulator til 5V)
  - Dedikert 5V/2A DC adapter
- **Kobling:** 
  - V+ og GND fra separat forsyning
  - **Ikke** koble V+ til Pi's 5V pin!
  - **Koble** GND fra separat forsyning til Pi's GND (felles ground)

---

## Software Konfigurasjon

### /boot/firmware/config.txt
```bash
# Aktiver I2C for PCA9685
dtparam=i2c_arm=on

# Aktiver I2S for MAX98357A
dtparam=i2s=on

# Google Voice HAT overlay for MAX98357A
dtoverlay=googlevoicehat-soundcard
```

### ~/.asoundrc
```
pcm.!default {
    type plug
    slave.pcm "softvol"
}

pcm.softvol {
    type softvol
    slave {
        pcm "dmixer"
    }
    control {
        name "Master"
        card 1
    }
    min_dB -30.0
    max_dB 0.0
}

pcm.dmixer {
    type dmix
    ipc_key 1024
    ipc_perm 0666
    slave {
        pcm "hw:1,0"
        period_time 0
        period_size 1024
        buffer_size 8192
        rate 48000
        format S32_LE
        channels 2
    }
    bindings {
        0 0
        1 1
    }
}

ctl.!default {
    type hw
    card 1
}
```

### Volum
```bash
# Sett ALSA Master volum til 70% (anbefalt med GAIN=GND)
amixer -c 1 sset Master 70%
```

---

## Feilsøking

### PCA9685 (Servo)
```bash
# Sjekk at I2C er aktivert
ls /dev/i2c*
# Skal vise: /dev/i2c-1

# Sjekk at PCA9685 er synlig (adresse 0x40)
i2cdetect -y 1
# Skal vise "40" i tabellen

# Test servo
python3 test_servo.py
```

### MAX98357A (Audio)
```bash
# Sjekk lydkort
aplay -l
# Skal vise: card 1: googlevoicehat

# Test lyd
speaker-test -t wav -c 2 -D hw:1,0

# Sjekk volum
alsamixer -c 1
```

### RGB LED
```bash
# Test LED direkte (krever lgpio)
python3 -c "import lgpio; h=lgpio.gpiochip_open(0); lgpio.gpio_claim_output(h, 17); lgpio.gpio_write(h, 17, 1)"
# Rød LED skal lyse
```

---

## Visualisering for Montering i Lekeand

```
┌──────────────────────────────────────┐
│      Raspberry Pi 5 (horisontal)     │
│  ┌──────────────────────────────┐    │
│  │   [3.3V] [5V] [GPIO2-GPIO3]  │    │
│  │    ↓↓↓    ↓↓   ↓↓↓↓          │    │
│  └────┬──────┬────┬──────────────┘    │
│       │      │    │                   │
│   PCA9685   MAX   GND (felles)       │
│    + Servo  98357A                    │
│             + Høyttaler               │
└──────────────────────────────────────┘

Plassering i and:
- Pi 5 i buken (flat)
- PCA9685 under Pi (I2C-kablet)
- MAX98357A på siden
- Servo i hodet (kobles til PCA9685 CH0)
- Høyttaler i brystet
- RGB LED i hodet/tut (synlig utenfra)
- USB mikrofon i nebbet/fremside
- Separat batteri for servo under Pi
```

---

## Komponent-Liste

| Komponent | Antall | Beskrivelse |
|-----------|--------|-------------|
| Raspberry Pi 5 | 1 | Hovedkontroller |
| PCA9685 16-CH PWM | 1 | Servo driver (I2C) |
| MAX98357A | 1 | I2S Class-D audio amp |
| Micro servo | 1 | Nebb-bevegelse |
| RGB LED | 1 | Status-indikator |
| USB mikrofon | 1 | Lydinngang |
| Høyttaler 4-8Ω | 1 | 3W+ anbefalt |
| 5V strømforsyning (servo) | 1 | USB power bank eller batterier |
| Jumper-kabler | 20-30 | Tilkoblinger |

---

## Referanser

- **PCA9685 Datasheet:** https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf
- **MAX98357A Datasheet:** https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf
- **Raspberry Pi Pinout:** https://pinout.xyz/
- **I2S Audio Guide:** https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp

---

**Oppdatert:** 2025-11-11  
**Versjon:** oDuckberry5 (Raspberry Pi 5 + MAX98357A + PCA9685)
