#!/usr/bin/env python3
"""
Web-kontrollpanel for ChatGPT Duck
Kjører på port 3000 for å starte/stoppe anda-servicen
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
import os
from datetime import datetime

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChatGPT Duck Control</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 {
            color: #ff9800;
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .duck-emoji {
            text-align: center;
            font-size: 4em;
            margin: 20px 0;
        }
        .status-box {
            padding: 20px;
            margin: 20px 0;
            border-radius: 10px;
            text-align: center;
            font-size: 1.2em;
            font-weight: bold;
        }
        .status-running {
            background: #d4edda;
            color: #155724;
            border: 2px solid #28a745;
        }
        .status-stopped {
            background: #f8d7da;
            color: #721c24;
            border: 2px solid #dc3545;
        }
        .status-unknown {
            background: #fff3cd;
            color: #856404;
            border: 2px solid #ffc107;
        }
        button {
            width: 100%;
            padding: 15px 30px;
            margin: 10px 0;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: bold;
            transition: all 0.3s;
        }
        .btn-start {
            background: #28a745;
            color: white;
        }
        .btn-start:hover {
            background: #218838;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(40,167,69,0.3);
        }
        .btn-stop {
            background: #dc3545;
            color: white;
        }
        .btn-stop:hover {
            background: #c82333;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(220,53,69,0.3);
        }
        .btn-restart {
            background: #ff9800;
            color: white;
        }
        .btn-restart:hover {
            background: #e68900;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255,152,0,0.3);
        }
        .btn-logs {
            background: #6c757d;
            color: white;
        }
        .btn-logs:hover {
            background: #5a6268;
        }
        .btn-speak {
            background: #9c27b0;
            color: white;
        }
        .btn-speak:hover {
            background: #7b1fa2;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(156,39,176,0.3);
        }
        .btn-wifi {
            background: #2196F3;
            color: white;
        }
        .btn-wifi:hover {
            background: #0b7dda;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(33,150,243,0.3);
        }
        .btn-shutdown {
            background: #d32f2f;
            color: white;
            margin-top: 20px;
        }
        .btn-shutdown:hover {
            background: #b71c1c;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(211,47,47,0.3);
        }
        .btn-reboot {
            background: #ff6f00;
            color: white;
        }
        .btn-reboot:hover {
            background: #e65100;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255,111,0,0.3);
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            box-sizing: border-box;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #4CAF50;
        }
        select {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            box-sizing: border-box;
            background: white;
            cursor: pointer;
        }
        select:focus {
            outline: none;
            border-color: #9c27b0;
        }
        .speak-section {
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .speak-section h3 {
            margin-top: 0;
            color: #9c27b0;
        }
        .info {
            margin-top: 30px;
            padding: 15px;
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            border-radius: 5px;
        }
        .info h3 {
            margin-top: 0;
            color: #1976D2;
        }
        #log-output {
            display: none;
            margin-top: 20px;
            padding: 15px;
            background: #000;
            color: #0f0;
            font-family: monospace;
            border-radius: 5px;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
        }
        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="duck-emoji">🦆</div>
        <h1>ChatGPT Duck</h1>
        
        <div id="status" class="status-box status-unknown">
            Henter status...
        </div>
        
        <button class="btn-start" onclick="controlDuck('start')">▶️ Start Duck</button>
        <button class="btn-stop" onclick="controlDuck('stop')">⏹️ Stopp Duck</button>
        <button class="btn-restart" onclick="controlDuck('restart')">🔄 Restart Duck</button>
        <button class="btn-logs" onclick="toggleLogs()">📋 Vis Logger</button>
        <button class="btn-wifi" onclick="switchToHotspot()">📡 Bytt WiFi-nettverk</button>
        <button class="btn-reboot" onclick="rebootPi()">🔄 Restart Pi</button>
        <button class="btn-shutdown" onclick="shutdownPi()">🔌 Skru av Pi</button>
        
        <div id="log-output" style="display: none; margin: 20px 0; padding: 20px; background: #1e1e1e; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #333; max-height: 400px; overflow-y: auto;">
            <div id="log-content" style="font-family: 'Courier New', monospace; font-size: 12px; color: #00ff00; line-height: 1.4; white-space: pre-wrap; word-break: break-all;">
                Laster logger...
            </div>
        </div>
        
        <div class="speak-section">
            <h3>🎙️ Wake Words</h3>
            <div id="wake-words-list" class="info" style="background: #e8f5e9; border-left-color: #4caf50;">
                <p style="margin: 0; color: #2e7d32;">Laster wake words...</p>
            </div>
        </div>
        
        <div class="speak-section">
            <h3>🤖 AI Modell</h3>
            <select id="model-select" onchange="changeModel()">
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4o-mini">GPT-4o Mini</option>
                <option value="o1-preview">O1 Preview</option>
                <option value="o1-mini">O1 Mini</option>
            </select>
            <span id="model-status"></span>
        </div>
        
        <div class="speak-section">
            <h3>🎭 Personlighet</h3>
            <select id="personality-select" onchange="changePersonality()">
                <option value="normal">Normal 🦆</option>
                <option value="frekk">Frekk & Sarkastisk 😏</option>
                <option value="vennlig">Vennlig & Entusiastisk 😊</option>
                <option value="akademisk">Akademisk & Detaljert 🎓</option>
                <option value="filosof">Filosofisk & Reflekterende 🤔</option>
                <option value="barnlig">Barnlig & Leken 🎉</option>
                <option value="senior">Senior & Sur 👴</option>
            </select>
            <span id="personality-status"></span>
        </div>
        
        <div class="speak-section">
            <h3>🎤 Stemme</h3>
            <select id="voice-select" onchange="changeVoice()">
                <option value="nb-NO-FinnNeural">Finn (Mann) 👨</option>
                <option value="nb-NO-IselinNeural">Iselin (Kvinne) 👩</option>
            </select>
            <span id="voice-status"></span>
        </div>
        
        <div class="speak-section">
            <h3>🦆 Nebbet</h3>
            <select id="beak-select" onchange="changeBeak()">
                <option value="on">Nebbet beveger seg 👄</option>
                <option value="off">Nebbet av 🔇</option>
            </select>
            <span id="beak-status"></span>
        </div>
        
        <div class="speak-section">
            <h3>🎚️ Talehastighet</h3>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span>🐌 Sakte</span>
                <input type="range" id="speed-slider" min="0" max="100" value="50" 
                       oninput="updateSpeedLabel()" onchange="changeSpeed()" 
                       style="flex: 1;">
                <span>🐇 Raskt</span>
            </div>
            <div style="text-align: center; margin-top: 10px; font-weight: bold;" id="speed-label">Normal hastighet</div>
            <span id="speed-status"></span>
        </div>
        
        <div class="speak-section">
            <h3>🦆💬 Start samtale</h3>
            <button class="btn-start" onclick="startConversation()">🎤 Start samtale nå</button>
        </div>
        
        <div class="speak-section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 15px; box-shadow: 0 8px 16px rgba(0,0,0,0.2);">
            <h3 style="color: white; margin-bottom: 20px; font-size: 20px;">� Send melding til anda</h3>
            <div style="margin-bottom: 15px;">
                <label style="color: white; font-weight: bold; display: block; margin-bottom: 8px;">Velg modus:</label>
                <select id="message-mode" style="width: 100%; padding: 12px; border-radius: 8px; border: 2px solid white; font-size: 16px; background: white; cursor: pointer; box-sizing: border-box;">
                    <option value="speak">🔊 Bare si det (TTS)</option>
                    <option value="ai">🤖 Send til AI (ChatGPT)</option>
                </select>
            </div>
            <textarea id="speak-text" rows="6" placeholder="Skriv din melding her..." style="width: 100%; padding: 15px; border-radius: 10px; border: 2px solid white; font-size: 16px; resize: vertical; min-height: 120px; font-family: Arial, sans-serif; box-sizing: border-box;"></textarea>
            <button class="btn-send" onclick="sendMessage()" style="width: 100%; margin-top: 15px; padding: 15px; font-size: 18px; font-weight: bold; background: white; color: #667eea; border: none; border-radius: 10px; cursor: pointer; transition: all 0.3s; box-sizing: border-box;" onmouseover="this.style.background='#f0f0f0'; this.style.transform='scale(1.02)'" onmouseout="this.style.background='white'; this.style.transform='scale(1)'">📤 Send melding</button>
            <div id="ai-response" style="margin-top: 20px; padding: 20px; background-color: rgba(255,255,255,0.95); border-radius: 10px; display: none; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                <strong style="color: #667eea; font-size: 16px;">🤖 AI Svar:</strong>
                <div id="response-text" style="margin-top: 10px; color: #333; line-height: 1.6;"></div>
            </div>
        </div>

        <div class="speak-section">
            <h3>🔊 Volum</h3>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span>🔉 Lavt</span>
                <input type="range" id="volume-slider" min="0" max="100" value="50" 
                       oninput="updateVolumeValue()" onchange="changeVolume()" 
                       style="flex: 1;">
                <span>🔊 Høyt</span>
            </div>
            <div style="text-align: center; margin-top: 10px;">
                <span id="volume-value" style="font-weight: bold;">50%</span>
                <span id="volume-status"></span>
            </div>
        </div>
        
        <div class="speak-section">
            <h3>🌀 Viftekontroll</h3>
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <button class="btn" onclick="setFanMode('auto')" style="flex: 1;">🤖 Auto</button>
                <button class="btn" onclick="setFanMode('on')" style="flex: 1;">✅ På</button>
                <button class="btn" onclick="setFanMode('off')" style="flex: 1;">⏸️ Av</button>
            </div>
            <div id="fan-status" style="text-align: center; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 8px; font-weight: bold;">
                <div id="fan-mode">Modus: Laster...</div>
                <div id="fan-temp" style="font-size: 24px; margin: 10px 0;">🌡️ --°C</div>
                <div id="fan-running">Status: Laster...</div>
            </div>
        </div>
        
        <div class="speak-section" style="background: linear-gradient(135deg, #e91e63 0%, #9c27b0 100%); padding: 25px; border-radius: 15px; box-shadow: 0 8px 16px rgba(0,0,0,0.2);">
            <h3 style="color: white; margin-bottom: 20px; font-size: 20px;">🎵 La anda synge!</h3>
            <select id="song-select" style="width: 100%; padding: 12px; border-radius: 8px; border: 2px solid white; font-size: 16px; background: white; margin-bottom: 15px; box-sizing: border-box;">
                <option value="">Velg en sang...</option>
            </select>
            <button class="btn-start" onclick="playSong()" style="width: 100%; margin-bottom: 10px; padding: 15px; font-size: 18px; font-weight: bold; background: white; color: #e91e63; border: none; border-radius: 10px; cursor: pointer; transition: all 0.3s; box-sizing: border-box;" onmouseover="this.style.background='#f0f0f0'; this.style.transform='scale(1.02)'" onmouseout="this.style.background='white'; this.style.transform='scale(1)'">🎤 Syng!</button>
            <button class="btn-stop" onclick="stopSong()" style="width: 100%; padding: 15px; font-size: 18px; font-weight: bold; background: rgba(255,255,255,0.2); color: white; border: 2px solid white; border-radius: 10px; cursor: pointer; transition: all 0.3s; box-sizing: border-box;" onmouseover="this.style.background='rgba(255,255,255,0.3)'; this.style.transform='scale(1.02)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'; this.style.transform='scale(1)'">⏹ Stopp syng</button>
            <div id="song-status" style="margin-top: 15px; padding: 15px; background: rgba(255,255,255,0.9); border-radius: 8px; display: none; color: #333;"></div>
        </div>
        
        <div class="speak-section">
            <h3>📊 Status og tester</h3>
            <button class="btn" onclick="getStatus()">🔍 Sjekk status</button>
            <button class="btn" onclick="testBeak()">🧪 Test nebbet</button>
            <div id="test-result"></div>
        </div>
        
        <div class="status-section">
            <h3>🌐 WiFi nettverk</h3>
            <div id="wifi-list">Laster...</div>
            <button class="btn" onclick="getWiFiNetworks()">🔄 Oppdater liste</button>
        </div>
        
    </div>
    
    <script>
        function updateVolumeValue() {
            const slider = document.getElementById('volume-slider');
            document.getElementById('volume-value').textContent = slider.value + '%';
        }

        function updateSpeedLabel() {
            const slider = document.getElementById('speed-slider');
            const label = document.getElementById('speed-label');
            const value = parseInt(slider.value);
            
            if (value < 25) {
                label.textContent = 'Veldig sakte 🐌';
            } else if (value < 45) {
                label.textContent = 'Litt sakte';
            } else if (value < 55) {
                label.textContent = 'Normal hastighet';
            } else if (value < 75) {
                label.textContent = 'Litt raskere';
            } else {
                label.textContent = 'Rask 🐇';
            }
        }

        async function changeSpeed() {
            const slider = document.getElementById('speed-slider');
            const statusElement = document.getElementById('speed-status');
            
            try {
                const response = await fetch('/change-speed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ speed: slider.value })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    statusElement.textContent = ' ✓';
                    setTimeout(() => statusElement.textContent = '', 2000);
                } else {
                    statusElement.textContent = ' ✗ Feil';
                }
            } catch (error) {
                statusElement.textContent = ' ✗ Feil: ' + error.message;
            }
        }

        async function loadCurrentSpeed() {
            try {
                const response = await fetch('/current-speed');
                const data = await response.json();
                const slider = document.getElementById('speed-slider');
                slider.value = data.speed;
                updateSpeedLabel();
            } catch (error) {
                console.error('Kunne ikke laste talehastighet:', error);
            }
        }

        async function changeVolume() {
            const slider = document.getElementById('volume-slider');
            const statusElement = document.getElementById('volume-status');
            updateVolumeValue();
            
            try {
                const response = await fetch('/change-volume', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ volume: slider.value })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    statusElement.textContent = ' ✓';
                    setTimeout(() => statusElement.textContent = '', 2000);
                } else {
                    statusElement.textContent = ' ✗ Feil';
                }
            } catch (error) {
                statusElement.textContent = ' ✗ Feil: ' + error.message;
            }
        }

        async function loadCurrentVolume() {
            try {
                const response = await fetch('/current-volume');
                const data = await response.json();
                const slider = document.getElementById('volume-slider');
                slider.value = data.volume;
                updateVolumeValue();
            } catch (error) {
                console.error('Kunne ikke laste volum:', error);
            }
        }

        async function setFanMode(mode) {
            try {
                const response = await fetch('/set-fan-mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: mode })
                });
                
                const data = await response.json();
                if (data.success) {
                    loadFanStatus();
                }
            } catch (error) {
                console.error('Kunne ikke endre viftemodus:', error);
            }
        }

        async function loadFanStatus() {
            try {
                const response = await fetch('/fan-status');
                const data = await response.json();
                
                const modeText = {
                    'auto': '🤖 Automatisk',
                    'on': '✅ Alltid på',
                    'off': '⏸️ Alltid av'
                };
                
                document.getElementById('fan-mode').textContent = 'Modus: ' + (modeText[data.mode] || data.mode);
                document.getElementById('fan-temp').innerHTML = `🌡️ ${data.temp}°C`;
                
                const runningIcon = data.running ? '🌀' : '⏸️';
                const runningText = data.running ? 'Vifte går' : 'Vifte står';
                document.getElementById('fan-running').innerHTML = `${runningIcon} ${runningText}`;
                
                // Fargekoding av temperatur
                const tempElement = document.getElementById('fan-temp');
                if (data.temp >= 60) {
                    tempElement.style.color = '#ff4444';
                } else if (data.temp >= 55) {
                    tempElement.style.color = '#ffaa00';
                } else {
                    tempElement.style.color = '#44ff44';
                }
            } catch (error) {
                console.error('Kunne ikke laste viftestatus:', error);
            }
        }

        async function changeBeak() {
            const select = document.getElementById('beak-select');
            const statusElement = document.getElementById('beak-status');
            
            try {
                const response = await fetch('/change-beak', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ beak: select.value })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    statusElement.textContent = ' ✓';
                    setTimeout(() => statusElement.textContent = '', 2000);
                } else {
                    statusElement.textContent = ' ✗ Feil';
                }
            } catch (error) {
                statusElement.textContent = ' ✗ Feil: ' + error.message;
            }
        }

        async function loadCurrentBeak() {
            try {
                const response = await fetch('/current-beak');
                const data = await response.json();
                const select = document.getElementById('beak-select');
                select.value = data.beak;
            } catch (error) {
                console.error('Kunne ikke laste nebbet-status:', error);
            }
        }

        async function changePersonality() {
            const select = document.getElementById('personality-select');
            const statusElement = document.getElementById('personality-status');
            
            try {
                const response = await fetch('/change-personality', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ personality: select.value })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    statusElement.textContent = ' ✓';
                    setTimeout(() => statusElement.textContent = '', 2000);
                } else {
                    statusElement.textContent = ' ✗ Feil';
                }
            } catch (error) {
                statusElement.textContent = ' ✗ Feil: ' + error.message;
            }
        }

        async function loadCurrentPersonality() {
            try {
                const response = await fetch('/current-personality');
                const data = await response.json();
                const select = document.getElementById('personality-select');
                select.value = data.personality;
            } catch (error) {
                console.error('Kunne ikke laste personlighet:', error);
            }
        }

        async function changeVoice() {
            const select = document.getElementById('voice-select');
            const statusElement = document.getElementById('voice-status');
            
            try {
                const response = await fetch('/change-voice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ voice: select.value })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    statusElement.textContent = ' ✓';
                    setTimeout(() => statusElement.textContent = '', 2000);
                } else {
                    statusElement.textContent = ' ✗ Feil';
                }
            } catch (error) {
                statusElement.textContent = ' ✗ Feil: ' + error.message;
            }
        }

        async function loadCurrentVoice() {
            try {
                const response = await fetch('/current-voice');
                const data = await response.json();
                const select = document.getElementById('voice-select');
                select.value = data.voice;
            } catch (error) {
                console.error('Kunne ikke laste stemme:', error);
            }
        }

        async function sendMessage() {
            const textarea = document.getElementById('speak-text');
            const mode = document.getElementById('message-mode').value;
            const text = textarea.value.trim();
            const responseDiv = document.getElementById('ai-response');
            const responseTextDiv = document.getElementById('response-text');
            
            if (!text) {
                alert('Skriv en melding først!');
                return;
            }
            
            if (mode === 'ai') {
                // Show loading state
                responseDiv.style.display = 'block';
                responseTextDiv.innerHTML = '<em>Venter på svar fra AI...</em>';
                
                try {
                    const response = await fetch('/ask-ai', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: text })
                    });
                    const data = await response.json();
                    
                    if (data.success === true) {
                        const aiResponseText = data.response || 'Ingen svar mottatt';
                        const formattedResponse = `<strong>Spørsmål:</strong> ${text}<br><br><strong>Svar:</strong> ${aiResponseText}`;
                        responseTextDiv.innerHTML = formattedResponse;
                        
                        // Legg til knapp for å få anda til å si svaret
                        const speakButton = document.createElement('button');
                        speakButton.textContent = '🔊 La anda si svaret';
                        speakButton.style.marginTop = '10px';
                        speakButton.style.width = '100%';
                        speakButton.onclick = async () => {
                            speakButton.disabled = true;
                            speakButton.textContent = '⏳ Sender til anda...';
                            try {
                                const fullText = `Du spurte om: ${text}. Her er svaret: ${aiResponseText}`;
                                const speakResponse = await fetch('/speak', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ text: fullText })
                                });
                                const speakData = await speakResponse.json();
                                if (speakData.success === true) {
                                    speakButton.textContent = '✓ Anda sier det nå!';
                                    setTimeout(() => {
                                        speakButton.disabled = false;
                                        speakButton.textContent = '🔊 La anda si svaret';
                                    }, 3000);
                                } else {
                                    speakButton.textContent = '❌ Feil ved sending';
                                    speakButton.disabled = false;
                                }
                            } catch (error) {
                                speakButton.textContent = '❌ Feil: ' + error.message;
                                speakButton.disabled = false;
                            }
                        };
                        responseTextDiv.appendChild(speakButton);
                    } else {
                        responseTextDiv.innerHTML = '<em style="color: red;">Feil: ' + (data.error || 'Ukjent feil') + '</em>';
                    }
                } catch (error) {
                    responseTextDiv.innerHTML = '<em style="color: red;">Feil: ' + error.message + '</em>';
                }
            } else {
                // Original speak functionality
                responseDiv.style.display = 'none';
                try {
                    const response = await fetch('/speak', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: text })
                    });
                    const data = await response.json();
                    
                    if (data.success === true) {
                        textarea.value = '';
                        alert('Melding sendt! ✓');
                    } else {
                        alert('Feil ved sending: ' + data.error);
                    }
                } catch (error) {
                    alert('Feil: ' + error.message);
                }
            }
        }

        async function startConversation() {
            try {
                const response = await fetch('/start-conversation', {
                    method: 'POST'
                });
                const data = await response.json();
                alert(data.message || 'Samtale startet!');
            } catch (error) {
                alert('Feil: ' + error.message);
            }
        }

        async function loadWakeWords() {
            try {
                const response = await fetch('/wake-words');
                const data = await response.json();
                if (data.wake_words) {
                    const wakeWordsList = document.getElementById('wake-words-list');
                    const wordsHtml = data.wake_words.map((word, i) => 
                        `<span style="display: inline-block; margin: 5px 8px; padding: 8px 16px; background: #4caf50; color: white; border-radius: 20px; font-weight: bold; font-size: 0.95em;">${word.charAt(0).toUpperCase() + word.slice(1)}</span>`
                    ).join('');
                    wakeWordsList.innerHTML = `<p style="margin: 0 0 10px 0; color: #2e7d32; font-weight: bold;">Aktive wake words:</p><div>${wordsHtml}</div>`;
                }
            } catch (error) {
                console.error('Feil ved lasting av wake words:', error);
            }
        }
        
        async function getStatus() {
            const resultDiv = document.getElementById('test-result');
            resultDiv.textContent = 'Henter status...';
            
            try {
                const response = await fetch('/status');
                const data = await response.json();
                resultDiv.innerHTML = `
                    <strong>Status:</strong><br>
                    Personlighet: ${data.personality}<br>
                    Stemme: ${data.voice}<br>
                    Volum: ${data.volume}%<br>
                    Nebbet: ${data.beak === 'on' ? 'På ✓' : 'Av ✗'}<br>
                    Talehastighet: ${data.speed}%
                `;
            } catch (error) {
                resultDiv.textContent = 'Feil: ' + error.message;
            }
        }

        async function testBeak() {
            const resultDiv = document.getElementById('test-result');
            resultDiv.textContent = 'Tester nebbet...';
            
            try {
                const response = await fetch('/test-beak', {
                    method: 'POST'
                });
                const data = await response.json();
                resultDiv.textContent = data.message || 'Test fullført!';
            } catch (error) {
                resultDiv.textContent = 'Feil: ' + error.message;
            }
        }

        async function getWiFiNetworks() {
            const listDiv = document.getElementById('wifi-list');
            listDiv.textContent = 'Skanner etter nettverk...';
            
            try {
                const response = await fetch('/wifi-networks');
                const data = await response.json();
                
                if (data.status === 'success' && data.networks) {
                    if (data.networks.length === 0) {
                        listDiv.textContent = 'Ingen nettverk funnet';
                    } else {
                        listDiv.innerHTML = '<ul>' + 
                            data.networks.map(net => `<li>${net.ssid} (${net.signal})</li>`).join('') + 
                            '</ul>';
                    }
                } else {
                    listDiv.textContent = 'Kunne ikke hente nettverk';
                }
            } catch (error) {
                listDiv.textContent = 'Feil: ' + error.message;
            }
        }

        async function updateStatus() {
            try {
                const response = await fetch('/duck-status');
                const data = await response.json();
                const statusEl = document.getElementById('status');
                
                if (data.running) {
                    statusEl.className = 'status-box status-running';
                    statusEl.innerHTML = '✅ Duck kjører';
                } else {
                    statusEl.className = 'status-box status-stopped';
                    statusEl.innerHTML = '⏸️ Duck er stoppet';
                }
            } catch (error) {
                const statusEl = document.getElementById('status');
                statusEl.className = 'status-box status-unknown';
                statusEl.innerHTML = '❓ Kunne ikke hente status';
            }
        }

        async function controlDuck(action) {
            try {
                const response = await fetch('/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: action })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    alert(data.message || 'Kommando utført!');
                    // Update status after action
                    setTimeout(() => updateStatus(), 1000);
                } else {
                    alert('Feil: ' + (data.error || 'Ukjent feil'));
                }
            } catch (error) {
                alert('Feil: ' + error.message);
            }
        }

        function toggleLogs() {
            const logDiv = document.getElementById('log-output');
            const logButton = document.querySelector('.btn-logs');
            
            if (logDiv.style.display === 'none' || !logDiv.style.display) {
                logDiv.style.display = 'block';
                logButton.textContent = '📋 Skjul Logger';
                // Start polling for logs
                if (!window.logInterval) {
                    fetchLogs();
                    window.logInterval = setInterval(fetchLogs, 2000);
                }
            } else {
                logDiv.style.display = 'none';
                logButton.textContent = '📋 Vis Logger';
                // Stop polling
                if (window.logInterval) {
                    clearInterval(window.logInterval);
                    window.logInterval = null;
                }
            }
        }

        async function fetchLogs() {
            try {
                const response = await fetch('/logs');
                const data = await response.json();
                const logContent = document.getElementById('log-content');
                
                if (data.logs) {
                    // Split logs into lines and add colors
                    const lines = data.logs.split('\\\\n');
                    const coloredLines = lines.map(function(line) {
                        const escapedLine = line.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                        if (line.includes('ERROR') || line.includes('error') || line.includes('failed')) {
                            return '<span style="color: #ff4444;">' + escapedLine + '</span>';
                        } else if (line.includes('WARNING') || line.includes('warning')) {
                            return '<span style="color: #ffaa00;">' + escapedLine + '</span>';
                        } else if (line.includes('INFO') || line.includes('Started') || line.includes('Active:')) {
                            return '<span style="color: #44ff44;">' + escapedLine + '</span>';
                        } else {
                            return '<span style="color: #88ff88;">' + escapedLine + '</span>';
                        }
                    }).join('<br>');
                    
                    // Check if user was at bottom before updating
                    const logOutput = document.getElementById('log-output');
                    const wasAtBottom = logOutput.scrollHeight - logOutput.scrollTop - logOutput.clientHeight < 50;
                    
                    logContent.innerHTML = coloredLines;
                    
                    // Only auto-scroll if user was already at bottom
                    if (wasAtBottom) {
                        logOutput.scrollTop = logOutput.scrollHeight;
                    }
                } else {
                    logContent.textContent = 'Ingen logger tilgjengelig';
                }
            } catch (error) {
                console.error('Kunne ikke hente logger:', error);
                const logContent = document.getElementById('log-content');
                logContent.innerHTML = '<span style="color: #ff4444;">Feil ved lasting av logger: ' + error.message + '</span>';
            }
        }

        async function switchToHotspot() {
            if (!confirm('Dette vil starte WiFi-portalen. Vil du fortsette?')) {
                return;
            }
            
            try {
                const response = await fetch('/start-portal', {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success === true) {
                    alert('WiFi-portal startet! Koble til "Hotspot" nettverk og gå til http://192.168.4.1');
                } else {
                    alert('Feil: ' + (data.error || 'Ukjent feil'));
                }
            } catch (error) {
                alert('Feil: ' + error.message);
            }
        }

        async function rebootPi() {
            if (!confirm('Er du sikker på at du vil restarte Raspberry Pi?')) {
                return;
            }
            
            try {
                const response = await fetch('/reboot', {
                    method: 'POST'
                });
                alert('Raspberry Pi restarter...');
            } catch (error) {
                alert('Feil: ' + error.message);
            }
        }

        async function shutdownPi() {
            if (!confirm('Er du sikker på at du vil skru av Raspberry Pi?')) {
                return;
            }
            
            try {
                const response = await fetch('/shutdown', {
                    method: 'POST'
                });
                alert('Raspberry Pi skrur av...');
            } catch (error) {
                alert('Feil: ' + error.message);
            }
        }

        async function changeModel() {
            const select = document.getElementById('model-select');
            const statusElement = document.getElementById('model-status');
            
            try {
                const response = await fetch('/change-model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: select.value })
                });
                const data = await response.json();
                
                if (data.success === true) {
                    statusElement.textContent = ' ✓';
                    setTimeout(() => statusElement.textContent = '', 2000);
                } else {
                    statusElement.textContent = ' ✗ Feil';
                }
            } catch (error) {
                statusElement.textContent = ' ✗ Feil: ' + error.message;
            }
        }

        async function loadCurrentModel() {
            try {
                const response = await fetch('/current-model');
                const data = await response.json();
                const select = document.getElementById('model-select');
                select.value = data.model;
            } catch (error) {
                console.error('Kunne ikke laste modell:', error);
            }
        }

        async function loadWakeWords() {
            try {
                const response = await fetch('/wake-words');
                const data = await response.json();
                if (data.wake_words) {
                    const wakeWordsList = document.getElementById('wake-words-list');
                    const wordsHtml = data.wake_words.map((word, i) => 
                        `<span style="display: inline-block; margin: 5px 8px; padding: 8px 16px; background: #4caf50; color: white; border-radius: 20px; font-weight: bold; font-size: 0.95em;">${word.charAt(0).toUpperCase() + word.slice(1)}</span>`
                    ).join('');
                    wakeWordsList.innerHTML = `<p style="margin: 0 0 10px 0; color: #2e7d32; font-weight: bold;">Aktive wake words:</p><div>${wordsHtml}</div>`;
                }
            } catch (error) {
                console.error('Feil ved lasting av wake words:', error);
            }
        }

        // Sang-funksjoner
        async function loadSongs() {
            try {
                const response = await fetch('/songs');
                const data = await response.json();
                const select = document.getElementById('song-select');
                
                // Tøm eksisterende alternativer (behold første "Velg en sang...")
                select.innerHTML = '<option value="">Velg en sang...</option>';
                
                if (data.songs && data.songs.length > 0) {
                    data.songs.forEach(song => {
                        const option = document.createElement('option');
                        option.value = song.path;
                        option.textContent = song.name;
                        select.appendChild(option);
                    });
                } else {
                    select.innerHTML += '<option value="" disabled>Ingen sanger funnet</option>';
                }
            } catch (error) {
                console.error('Kunne ikke laste sanger:', error);
            }
        }
        
        async function playSong() {
            const select = document.getElementById('song-select');
            const statusDiv = document.getElementById('song-status');
            const songPath = select.value;
            
            if (!songPath) {
                alert('Velg en sang først!');
                return;
            }
            
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '<strong>🎤 Anda synger nå...</strong>';
            
            try {
                const response = await fetch('/play-song', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ song_path: songPath })
                });
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.innerHTML = '<strong style="color: #4caf50;">✓ Sang startet!</strong>';
                    setTimeout(() => statusDiv.style.display = 'none', 5000);
                } else {
                    statusDiv.innerHTML = '<strong style="color: #f44336;">✗ Feil: ' + (data.error || 'Ukjent feil') + '</strong>';
                }
            } catch (error) {
                statusDiv.innerHTML = '<strong style="color: #f44336;">✗ Feil: ' + error.message + '</strong>';
            }
        }
        
        async function stopSong() {
            const statusDiv = document.getElementById('song-status');
            
            try {
                const response = await fetch('/stop-song', {method: 'POST'});
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.style.display = 'block';
                    statusDiv.innerHTML = '<strong style="color: #ff9800;">⏹ Sang stoppet</strong>';
                    setTimeout(() => statusDiv.style.display = 'none', 3000);
                } else {
                    alert('Feil ved stopp av sang');
                }
            } catch (error) {
                alert('Feil: ' + error.message);
            }
        }

        // Load current settings on page load
        window.onload = function() {
            updateStatus();
            loadWakeWords();
            loadCurrentModel();
            loadCurrentPersonality();
            loadCurrentVoice();
            loadCurrentVolume();
            loadCurrentBeak();
            loadCurrentSpeed();
            loadFanStatus();
            getWiFiNetworks();
            loadSongs();  // Last sanger
            
            // Oppdater status automatisk hvert 5. sekund
            setInterval(updateStatus, 5000);
            setInterval(loadFanStatus, 5000);
        };
    </script>
</body>
</html>
"""

class DuckControlHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())
        
        elif self.path == '/favicon.ico':
            # Return 204 No Content for favicon to avoid console errors
            self.send_response(204)
            self.end_headers()
        
        elif self.path == '/status':
            # Hent alle innstillinger for status
            try:
                # Personlighet
                personality_file = '/tmp/duck_personality.txt'
                personality = 'normal'
                if os.path.exists(personality_file):
                    with open(personality_file, 'r') as f:
                        personality = f.read().strip() or 'normal'
                
                # Stemme
                voice_file = '/tmp/duck_voice.txt'
                voice = 'nb-NO-FinnNeural'
                if os.path.exists(voice_file):
                    with open(voice_file, 'r') as f:
                        voice = f.read().strip() or 'nb-NO-FinnNeural'
                
                # Volum
                volume_file = '/tmp/duck_volume.txt'
                volume = 50
                if os.path.exists(volume_file):
                    with open(volume_file, 'r') as f:
                        volume = int(f.read().strip() or '50')
                
                # Nebbet
                beak_file = '/tmp/duck_beak.txt'
                beak = 'on'
                if os.path.exists(beak_file):
                    with open(beak_file, 'r') as f:
                        beak = f.read().strip() or 'on'
                
                # Hastighet
                speed_file = '/tmp/duck_speed.txt'
                speed = 50
                if os.path.exists(speed_file):
                    with open(speed_file, 'r') as f:
                        speed = int(f.read().strip() or '50')
                
                response = {
                    'personality': personality,
                    'voice': voice,
                    'volume': volume,
                    'beak': beak,
                    'speed': speed
                }
            except Exception as e:
                response = {
                    'personality': 'normal',
                    'voice': 'nb-NO-FinnNeural',
                    'volume': 50,
                    'beak': 'on',
                    'speed': 50,
                    'error': str(e)
                }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/duck-status':
            # Sjekk om duck-service kjører
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                running = result.stdout.strip() == 'active'
                response = {'running': running}
            except Exception as e:
                response = {'running': False, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/logs':
            # Hent siste logger
            try:
                result = subprocess.run(
                    ['sudo', 'journalctl', '-u', 'chatgpt-duck.service', '-n', '50', '--no-pager'],
                    capture_output=True, text=True, timeout=5
                )
                response = {'logs': result.stdout}
            except Exception as e:
                response = {'logs': f'Feil ved henting av logger: {e}'}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-model':
            # Hent gjeldende AI-modell
            try:
                model_file = '/tmp/duck_model.txt'
                default_model = 'gpt-3.5-turbo'
                
                if os.path.exists(model_file):
                    with open(model_file, 'r') as f:
                        model = f.read().strip()
                        if not model:
                            model = default_model
                else:
                    model = default_model
                
                response = {'model': model}
            except Exception as e:
                response = {'model': 'gpt-3.5-turbo', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-personality':
            # Hent gjeldende personlighet
            try:
                personality_file = '/tmp/duck_personality.txt'
                default_personality = 'normal'
                
                if os.path.exists(personality_file):
                    with open(personality_file, 'r') as f:
                        personality = f.read().strip()
                        if not personality:
                            personality = default_personality
                else:
                    personality = default_personality
                
                response = {'personality': personality}
            except Exception as e:
                response = {'personality': 'normal', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-voice':
            # Hent gjeldende TTS-stemme
            try:
                voice_file = '/tmp/duck_voice.txt'
                default_voice = 'nb-NO-FinnNeural'
                
                if os.path.exists(voice_file):
                    with open(voice_file, 'r') as f:
                        voice = f.read().strip()
                        if not voice:
                            voice = default_voice
                else:
                    voice = default_voice
                
                response = {'voice': voice}
            except Exception as e:
                response = {'voice': 'nb-NO-FinnNeural', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-beak':
            # Hent gjeldende nebbet-status
            try:
                beak_file = '/tmp/duck_beak.txt'
                default_beak = 'on'
                
                if os.path.exists(beak_file):
                    with open(beak_file, 'r') as f:
                        beak = f.read().strip()
                        if not beak:
                            beak = default_beak
                else:
                    beak = default_beak
                
                response = {'beak': beak}
            except Exception as e:
                response = {'beak': 'on', 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-speed':
            # Hent gjeldende talehastighet
            try:
                speed_file = '/tmp/duck_speed.txt'
                default_speed = '50'
                
                if os.path.exists(speed_file):
                    with open(speed_file, 'r') as f:
                        speed = f.read().strip()
                        if not speed:
                            speed = default_speed
                else:
                    speed = default_speed
                
                response = {'speed': int(speed)}
            except Exception as e:
                response = {'speed': 50, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/current-volume':
            # Hent gjeldende volum
            try:
                volume_file = '/tmp/duck_volume.txt'
                default_volume = '50'
                
                if os.path.exists(volume_file):
                    with open(volume_file, 'r') as f:
                        volume = f.read().strip()
                        if not volume:
                            volume = default_volume
                else:
                    volume = default_volume
                
                response = {'volume': int(volume)}
            except Exception as e:
                response = {'volume': 50, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/wake-words':
            # Returner liste over aktive wake words (Porcupine)
            try:
                wake_words = ['Samantha', 'quack quack']
                response = {'wake_words': wake_words}
            except Exception as e:
                response = {'error': str(e), 'wake_words': []}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/fan-status':
            # Hent viftestatus
            try:
                status_file = '/tmp/duck_fan_status.txt'
                if os.path.exists(status_file):
                    with open(status_file, 'r') as f:
                        data = f.read().strip().split('|')
                        if len(data) == 3:
                            response = {
                                'mode': data[0],
                                'running': data[1].lower() == 'true',
                                'temp': float(data[2])
                            }
                        else:
                            response = {'mode': 'auto', 'running': False, 'temp': 0.0}
                else:
                    response = {'mode': 'auto', 'running': False, 'temp': 0.0}
            except Exception as e:
                response = {'mode': 'auto', 'running': False, 'temp': 0.0, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/songs':
            # Hent liste over tilgjengelige sanger
            try:
                music_dir = '/home/admog/Code/chatgpt-and/musikk'
                songs = []
                
                if os.path.exists(music_dir):
                    for artist_song in os.listdir(music_dir):
                        song_path = os.path.join(music_dir, artist_song)
                        if os.path.isdir(song_path):
                            # Sjekk om begge filene finnes
                            mix_file = os.path.join(song_path, 'duck_mix.wav')
                            vocals_file = os.path.join(song_path, 'vocals_duck.wav')
                            if os.path.exists(mix_file) and os.path.exists(vocals_file):
                                songs.append({
                                    'name': artist_song,
                                    'path': song_path
                                })
                
                # Sorter alfabetisk
                songs.sort(key=lambda x: x['name'])
                response = {'songs': songs}
            except Exception as e:
                response = {'songs': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/wifi-networks':
            # Hent tilgjengelige WiFi-nettverk
            try:
                result = subprocess.run(
                    ['sudo', 'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list'],
                    capture_output=True, text=True, timeout=10
                )
                
                networks = []
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                ssid = parts[0]
                                signal = parts[1] if len(parts) > 1 else '0'
                                if ssid and ssid != '--':
                                    networks.append({
                                        'ssid': ssid,
                                        'signal': signal + '%'
                                    })
                
                response = {'status': 'success', 'networks': networks}
            except Exception as e:
                response = {'status': 'error', 'networks': [], 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/ask-ai':
            # Send melding til AI og få respons direkte via OpenAI API
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            text = data.get('text', '').strip()
            print(f"AI-spørsmål: {text}", flush=True)
            
            if not text:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen tekst'}).encode())
                return
            
            try:
                # Import nødvendige moduler
                import os as _os
                import requests
                from dotenv import load_dotenv
                
                # Les personlighet og modell
                personality_file = '/tmp/duck_personality.txt'
                personality = 'normal'
                if _os.path.exists(personality_file):
                    with open(personality_file, 'r') as f:
                        personality = f.read().strip() or 'normal'
                
                model_file = '/tmp/duck_model.txt'
                model = 'gpt-3.5-turbo'
                if _os.path.exists(model_file):
                    with open(model_file, 'r') as f:
                        model = f.read().strip() or 'gpt-3.5-turbo'
                
                # Les API-nøkkel fra .env
                load_dotenv()
                api_key = _os.getenv('OPENAI_API_KEY')
                
                if not api_key:
                    raise Exception('OPENAI_API_KEY ikke funnet i .env')
                
                # Kall OpenAI API
                
                # Hent nåværende dato og tid
                from datetime import datetime as dt
                now = dt.now()
                date_time_info = f"Nåværende dato og tid: {now.strftime('%A %d. %B %Y, klokken %H:%M')}. "
                
                system_prompts = {
                    'normal': 'Du er en hjelpsom assistent.',
                    'entusiastic': 'Du er veldig energisk og entusiastisk!',
                    'philosophical': 'Du er en dyp tenker som reflekterer over livet.',
                    'humorous': 'Du er morsom og spøkefull.',
                    'concise': 'Du svarer kort og konsist.'
                }
                
                system_prompt = date_time_info + system_prompts.get(personality, system_prompts['normal'])
                
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': text}
                    ],
                    'max_tokens': 500,
                    'temperature': 0.7
                }
                
                api_response = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if api_response.status_code == 200:
                    result = api_response.json()
                    ai_text = result['choices'][0]['message']['content'].strip()
                    
                    response = {'success': True, 'response': ai_text}
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                else:
                    error_msg = f'OpenAI API error: {api_response.status_code}'
                    response = {'success': False, 'error': error_msg}
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                print(f"Feil i /ask-ai: {e}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/control':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            action = data.get('action')
            print(f"Handling: {action}", flush=True)
            
            try:
                if action == 'start':
                    cmd = ['sudo', 'systemctl', 'start', 'chatgpt-duck.service']
                elif action == 'stop':
                    cmd = ['sudo', 'systemctl', 'stop', 'chatgpt-duck.service']
                elif action == 'restart':
                    cmd = ['sudo', 'systemctl', 'restart', 'chatgpt-duck.service']
                else:
                    raise ValueError(f"Ugyldig handling: {action}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    response = {'success': True}
                else:
                    response = {'success': False, 'error': result.stderr}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/control':
            # Kontroller duck-servicen (start/stop/restart)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            action = data.get('action', '').strip()
            print(f"Control action: {action}", flush=True)
            
            if action not in ['start', 'stop', 'restart']:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ugyldig action'}).encode())
                return
            
            try:
                result = subprocess.run(
                    ['sudo', 'systemctl', action, 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    response = {'success': True, 'message': f'Duck {action}ed'}
                else:
                    response = {'success': False, 'error': result.stderr or 'Ukjent feil'}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/test-beak':
            # Test nebbet ved å sende en testmelding
            print("Testing beak...", flush=True)
            
            try:
                # Send en testmelding til duck
                message_file = '/tmp/duck_message.txt'
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write('Testing nebbet nå')
                
                response = {'success': True, 'message': 'Nebbet-test sendt!'}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/speak':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            text = data.get('text', '').strip()
            print(f"Speak request: {text}", flush=True)
            
            if not text:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen tekst angitt'}).encode())
                return
            
            try:
                # Sjekk om tjenesten kjører
                result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.stdout.strip() != 'active':
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Duck-servicen kjører ikke'}).encode())
                    return
                
                # Skriv melding til fil som duck-servicen sjekker
                message_file = '/tmp/duck_message.txt'
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/start-portal':
            # Start bare wifi-portal uten å bytte til hotspot
            print("Starting wifi-portal on port 80", flush=True)
            
            try:
                import os
                script_dir = os.path.dirname(os.path.abspath(__file__))
                
                # Tving WiFi-scan for å oppdatere tilgjengelige nettverk
                subprocess.run(
                    ['nmcli', 'device', 'wifi', 'rescan'],
                    capture_output=True,
                    timeout=5
                )
                
                # Sjekk om wifi-portal allerede kjører
                check_portal = subprocess.run(
                    ['pgrep', '-f', 'wifi-portal.py'],
                    capture_output=True
                )
                
                if check_portal.returncode == 0:
                    # Allerede kjører
                    response = {'success': True, 'message': 'Portal kjører allerede'}
                else:
                    # Start portal
                    portal_path = os.path.join(script_dir, 'wifi-portal.py')
                    subprocess.Popen(
                        ['python3', portal_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    response = {'success': True, 'message': 'Portal startet'}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/shutdown':
            # Shutdown Raspberry Pi
            print("Shutting down Raspberry Pi", flush=True)
            
            try:
                # Kjør shutdown kommando
                subprocess.Popen(
                    ['sudo', 'shutdown', '-h', '+0'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/reboot':
            # Reboot Raspberry Pi
            print("Rebooting Raspberry Pi", flush=True)
            
            try:
                # Kjør reboot kommando
                subprocess.Popen(
                    ['sudo', 'reboot'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-personality':
            # Endre personlighet
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            personality = data.get('personality')
            print(f"Endrer personlighet til: {personality}", flush=True)
            
            try:
                # Skriv personlighet til fil
                personality_file = '/tmp/duck_personality.txt'
                with open(personality_file, 'w', encoding='utf-8') as f:
                    f.write(personality)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-voice':
            # Endre TTS-stemme
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            voice = data.get('voice')
            print(f"Endrer TTS-stemme til: {voice}", flush=True)
            
            try:
                # Skriv stemme til fil
                voice_file = '/tmp/duck_voice.txt'
                with open(voice_file, 'w', encoding='utf-8') as f:
                    f.write(voice)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-beak':
            # Endre nebbet-status (on/off)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            beak = data.get('beak')
            print(f"Endrer nebbet til: {beak}", flush=True)
            
            try:
                # Skriv nebbet-status til fil
                beak_file = '/tmp/duck_beak.txt'
                with open(beak_file, 'w', encoding='utf-8') as f:
                    f.write(beak)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-speed':
            # Endre talehastighet (0-100, hvor 50 er normal)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            speed = int(data.get('speed', 50))
            # Clamp til 0-100
            speed = max(0, min(100, speed))
            
            print(f"Endrer talehastighet til: {speed}", flush=True)
            
            try:
                # Skriv hastighet til fil
                speed_file = '/tmp/duck_speed.txt'
                with open(speed_file, 'w', encoding='utf-8') as f:
                    f.write(str(speed))
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-volume':
            # Endre volum (0-100)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            volume = int(data.get('volume', 50))
            # Clamp til 0-100
            volume = max(0, min(100, volume))
            
            print(f"Endrer volum til: {volume}", flush=True)
            
            try:
                # Skriv volum til fil
                volume_file = '/tmp/duck_volume.txt'
                with open(volume_file, 'w', encoding='utf-8') as f:
                    f.write(str(volume))
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/set-fan-mode':
            # Endre viftemodus (auto/on/off)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            mode = data.get('mode', 'auto').lower()
            if mode not in ['auto', 'on', 'off']:
                mode = 'auto'
            
            print(f"Endrer viftemodus til: {mode}", flush=True)
            
            try:
                # Skriv modus til fil
                mode_file = '/tmp/duck_fan.txt'
                with open(mode_file, 'w', encoding='utf-8') as f:
                    f.write(mode)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/start-conversation':
            # Trigger en samtale uten wake word
            print("Starting conversation without wake word", flush=True)
            
            try:
                # Sjekk om servicen kjører
                result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.stdout.strip() != 'active':
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Duck-servicen kjører ikke'}).encode())
                    return
                
                # Skriv spesiell trigger til fil som duck-servicen sjekker
                message_file = '/tmp/duck_message.txt'
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write('__START_CONVERSATION__')
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/change-model':
            # Endre AI-modell
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            model = data.get('model')
            print(f"Endrer AI-modell til: {model}", flush=True)
            
            try:
                # Skriv modell til fil
                model_file = '/tmp/duck_model.txt'
                with open(model_file, 'w', encoding='utf-8') as f:
                    f.write(model)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/play-song':
            # Spill av en sang
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            song_path = data.get('song_path', '').strip()
            print(f"Sang-forespørsel: {song_path}", flush=True)
            
            if not song_path:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Ingen sang valgt'}).encode())
                return
            
            try:
                # Sjekk om servicen kjører
                result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', 'chatgpt-duck.service'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.stdout.strip() != 'active':
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Duck-servicen kjører ikke'}).encode())
                    return
                
                # Skriv sangforespørsel til fil
                song_request_file = '/tmp/duck_song_request.txt'
                with open(song_request_file, 'w', encoding='utf-8') as f:
                    f.write(song_path)
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        elif self.path == '/stop-song':
            # Stopp sang
            print("Stopp sang-forespørsel", flush=True)
            
            try:
                # Skriv stopp-forespørsel til fil
                song_stop_file = '/tmp/duck_song_stop.txt'
                with open(song_stop_file, 'w', encoding='utf-8') as f:
                    f.write('stop')
                
                response = {'success': True}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}", flush=True)

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 3000), DuckControlHandler)
    print("🦆 Duck Control Panel kjører på http://0.0.0.0:3000")
    print("   Tilgjengelig på: http://oduckberry:3000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutter...")
        server.shutdown()
