# ChatGPT Duck - Intelligent Duck 🦆

A complete AI-based voice assistant system with ChatGPT, Azure Speech Services, physical beak movement, RGB LED status, and web-based control panel.

[![Version](https://img.shields.io/badge/version-2.1.1-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

**[English documentation](docs/README_EN.md)** | **[Norsk dokumentasjon](../README.md)**

## 📚 Documentation

- **[DOCUMENTATION.md](DOCUMENTATION.md)** - 📋 Documentation overview
- **[INSTALL.md](INSTALL.md)** - 🔧 Complete installation guide (start here!)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 🏗️ Technical architecture and design
- **[PORTS.md](PORTS.md)** - 🌐 Network and port configuration
- **[CHANGELOG.md](CHANGELOG.md)** - 📝 Version history and new features

## Main Features

- 🎤 **Wake Word Detection**: Offline wake word (Vosk) - say "alexa" or "ulrika"
- 💬 **ChatGPT Conversations**: Natural dialogue with AI personalities
- 🗣️ **Azure TTS**: High-quality Norwegian text-to-speech with multiple voices
- 👄 **Synchronized Beak Movement**: Servo-controlled beak that moves to the sound
- 💡 **RGB LED Status**: Visual feedback for all system states
- 🌐 **Web Control Panel**: Complete remote control via browser
- 📊 **Real-time Logs**: Live system logs and status monitoring
- 🔧 **Adjustable Speech Speed**: From slow to lightning-fast speech
- 🔊 **Volume Control**: Adjust sound level in real-time
- 🌀 **Automatic Fan Control**: Temperature-based cooling with manual override
- 🎭 **Multiple Personalities**: Choose between different AI personalities
- 📱 **WiFi Portal**: Built-in WiFi setup for easy configuration

## ⚡ Quick Start

```bash
# 1. Install system packages
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv portaudio19-dev ffmpeg

# 2. Clone and setup
git clone https://github.com/Osmund/chatgpt-and.git
cd chatgpt-and
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Create .env with API keys
cat > .env << EOF
OPENAI_API_KEY=sk-your-key
AZURE_TTS_KEY=your-key
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=your-key
AZURE_STT_REGION=westeurope
EOF

# 4. Download Vosk model
wget https://alphacephei.com/vosk/models/vosk-model-small-sv-rhasspy-0.15.zip
unzip vosk-model-small-sv-rhasspy-0.15.zip

# 5. Install and start services
sudo ./scripts/install-services.sh
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service

# 6. Open control panel in browser
# http://<pi-ip>:3000
```

**For detailed guide, see [INSTALL.md](INSTALL.md)**

## Hardware

- Raspberry Pi (tested on Pi 400 and Pi 5)
- Monk Makes RGB LED (connected: R=GPIO17, G=GPIO27, B=GPIO22)
- USB-C PD-trigger with clipped USB-C cable connected to Pi
- PCA9685 servo controller (connected to PD-trigger for 5V power)
- Beak servo (connected to PCA9685 channel 0) - **NB: Power from PD-trigger, not Pi!**
- Microphone (USB or Pi-compatible)
- Speaker (3.5mm jack or USB)

## Hardware & Software Changes (Pi 5 / MAX98357A) - 2025-11-11

This project is updated for Raspberry Pi 5 and for use with a MAX98357A I2S Class-D amplifier. Below are brief instructions and explanations of choices and changes made during development.

### Hardware (recommended wiring)

**MAX98357A (I2S mono amp):**
- VCC → 5V or 3.3V depending on board (check your module)
- GND → GND
- DIN → GPIO21 (PCM_DOUT / I2S Data)
- BCLK → GPIO18 (PCM_CLK / Bit Clock)
- LRCK/WS (LRCLK) → GPIO19 (PCM_FS / Word Select)
- SD (shutdown / enable) → Connect to fixed 3.3V (pin 1 or 17) for "always on",
  alternatively SD can be controlled from a GPIO if you want to turn off the amplifier between playbacks.
- GAIN → Connect to GND for lower gain (9dB) if pop or distortion
  is a problem (default is 15dB when GAIN floats or is to VCC).

Note: Connecting GAIN to GND reduces gain and often reduces start/stop pop
significantly. If you experience residual pop, consider a DC-blocking capacitor
between speaker outputs (SPK+/SPK-) or switch to a DAC/amp with built-in
pop-suppression.

**PCA9685 servo driver (beak servo):**
- I2C SDA → GPIO2
- I2C SCL → GPIO3
- Servo signal → selected channel (default channel 0 in `duck_beak.py`)
- VCC (logic) → 3.3V from Pi
- V+ (servo power) → 5V from USB-C PD-trigger
- **Important**: USB-C PD-trigger with clipped cable provides stable 5V to servo controller
- This prevents the servo from drawing power directly from Pi (prevents reboots)

### Software / Code Changes

**duck_beak.py:**
- Migrated from pigpio to `adafruit_servokit` which talks to a PCA9685 over I2C.
- Configuration: `SERVO_CHANNEL`, `CLOSE_DEG`, `OPEN_DEG`, and pulse width range
  (`CLOSE_US_DEFAULT` / `OPEN_US_DEFAULT`) are at the top of the file for easy calibration.

**chatgpt_voice.py:**
- Supports I2S (Google Voice HAT / MAX98357A). Changes that were considered/implemented
  during development included: SD pin control via GPIO, pre/post silence, and
  fade-in/fade-out to reduce pop on Class-D amplifier.
- Final recommendation in this project: connect `SD` to 3.3V and `GAIN` to GND,
  and set ALSA Master (~70%) for best combination of volume and low distortion.
- If you want to do further troubleshooting: check `journalctl -u chatgpt-duck.service` and
  `alsamixer -c 1`.

### ALSA / Sound Setup

- A recommended `.asoundrc` is included to use softvol + dmix and S32_LE format
  for Google Voice HAT. If you switch to USB audio, update `pcm` settings
  or let `aplay -l` / `sd.query_devices()` show devices.

### Tips for minimal size (inside toy duck)

- MAX98357A is compact and still the best alternative when space is critical.
- If you want to eliminate pop completely, consider a DAC/HAT with pop-suppression
  (e.g., HifiBerry / PCM5102A-based modules), but they take more space and/or
  require additional power supply.

## Startup Message

At startup, the duck announces its IP address if the network is available:
- **With network**: "Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er [IP]. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!"
- **Without network**: "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"

The duck tries to connect to the network for up to 10 seconds before giving up and announcing that it has no connection.

## RGB LED Status Indicators

The RGB LED provides visual feedback for all system states:

| Color | Meaning |
|-------|---------|
| 🔵 Blue | Waiting for wake word ("alexa" or "ulrika") |
| 🟢 Green | Listening - speak now! |
| 🟡 Yellow blinking | Sending to Azure Speech Recognition |
| 🟣 Purple blinking | Waiting for ChatGPT response |
| 🔴 Red | Duck speaking (TTS active) |
| ⚪ Off | Idle/rest mode |

## Voice Commands

- **"alexa"** or **"ulrika"**: Activate duck (wake word)
- **"stopp"** or **"takk"**: End conversation and return to wake word mode
- Speak naturally - the duck understands context and can conduct longer conversations

## Web Control Panel

The system includes a complete web-based control panel available at `http://<raspberry-pi-ip>:3000`

### Control Panel Features

#### 🎮 Service Control
- **Start/Stop/Restart**: Full control over duck service
- **Real-time Status**: Automatic update every 5 seconds
- **Logs**: Live system log viewing with color-coded output

#### 🤖 AI Configuration
- **Model Selection**: Choose between ChatGPT models
  - `gpt-3.5-turbo` (fast, cheap)
  - `gpt-4` (smarter, more expensive)
  - `gpt-4-turbo` (balance)
- **Personalities**:
  - Normal (balanced and polite)
  - Enthusiastic (energetic and positive)
  - Philosophical (reflective and deep)
  - Humorous (funny and playful)
  - Short (concise answers)

#### 🗣️ Voice and Sound
- **Voice Selection**: Choose Azure TTS voice
  - `nb-NO-FinnNeural` (male, deep voice)
  - `nb-NO-PernilleNeural` (female, clear voice)
  - `nb-NO-IselinNeural` (female, warm voice)
- **Volume Control**: Adjust sound level 0-100% in real-time
  - 0%: Silent (no sound)
  - 50%: Normal volume (gain 1.0)
  - 100%: Double volume (gain 2.0)
- **Speech Speed**: Adjust speed from slow (0%) to lightning-fast (100%)
  - 0%: Very slow (–50% speed)
  - 50%: Normal speed
  - 100%: Double speed (+100%)

#### 👄 Beak Control
- **On/Off**: Enable or disable beak movement
- **Test**: Send test message to verify functionality

#### 🌀 Fan Control
- **Automatic mode**: Starts fan at 55°C, stops at 50°C
- **Manual override**: Force fan on or off
- **Real-time temperature display**: Color-coded (green < 55°C, orange < 60°C, red ≥ 60°C)
- **Live status**: See if fan is running right now

#### 💬 Send Messages
Three modes for direct communication:
- **🔊 Just say it (TTS)**: Duck reads the message without AI processing
- **🤖 Send to ChatGPT (silent)**: AI responds without sound
- **🎯 Full processing**: AI responds with speech and beak movement

## Systemd Services

The project runs as systemd services for automatic startup and management.

### Install Services

```bash
cd /home/admog/Code/chatgpt-and
sudo ./scripts/install-services.sh
```

This installs:
- `chatgpt-duck.service` - Main application
- `duck-control.service` - Web control panel (port: 3000)
- `auto-hotspot.service` - WiFi hotspot when needed

### Service Commands

```bash
# Start services
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service

# Stop services
sudo systemctl stop chatgpt-duck.service
sudo systemctl stop duck-control.service

# Restart
sudo systemctl restart chatgpt-duck.service

# View status
sudo systemctl status chatgpt-duck.service

# View logs
sudo journalctl -u chatgpt-duck.service -f
sudo journalctl -u duck-control.service -f

# Enable automatic startup at boot
sudo systemctl enable chatgpt-duck.service
sudo systemctl enable duck-control.service
```

## System Requirements

### Hardware
- **Raspberry Pi**: Pi 4, Pi 5, or Pi 400 (minimum 2GB RAM)
- **Microphone**: USB microphone or HAT with microphone
- **Speaker**: 3.5mm jack, HDMI, or USB speaker
- **RGB LED**: Monk Makes RGB LED or similar (GPIO 17, 27, 22)
- **Servo**: SG90 or similar 5V servo for beak (connected to PCA9685)
- **Power Supply**:
  - 5V/3A to Raspberry Pi
  - **USB-C PD-trigger for servo power** (important for stability!)

### Software
- **OS**: Raspberry Pi OS (Bookworm or newer)
- **Python**: 3.9 or newer
- **Systemd**: For service management
- **NetworkManager**: For WiFi management

### Network Requirements
- Internet connection (for ChatGPT and Azure APIs)
- Port 3000 open for web control panel

### API Keys (required)
- **OpenAI API Key**: For ChatGPT (https://platform.openai.com/api-keys)
- **Azure Speech Service**: For TTS and STT (https://portal.azure.com)
  - Region: Recommended `westeurope` or `northeurope`
  - Both Speech-to-Text and Text-to-Speech must be enabled

---

**Happy duck chatting! 🦆💬**
