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
            const lines = data.logs.split('\\n');
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
        // Først last inn tilgjengelige modeller
        await loadAvailableModels();
        
        // Deretter sett current model
        const response = await fetch('/current-model');
        const data = await response.json();
        const select = document.getElementById('model-select');
        if (select && data.model) {
            select.value = data.model;
        }
    } catch (error) {
        console.error('Kunne ikke laste modell:', error);
        // Fallback: Legg til minst noen modeller hvis API feiler
        loadFallbackModels();
    }
}

async function loadAvailableModels() {
    try {
        const response = await fetch('/available-models');
        if (!response.ok) {
            console.warn('API returned ' + response.status + ', keeping default models');
            return; // Behold modeller fra HTML
        }
        
        const data = await response.json();
        
        if (data.models && data.models.length > 0) {
            const select = document.getElementById('model-select');
            if (!select) {
                console.error('model-select element not found');
                return;
            }
            
            // Oppdater eksisterende modeller i stedet for å erstatte
            select.innerHTML = ''; // Tøm for å legge til oppdaterte
            
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                
                // Bygg visningsnavn
                let displayName = model.name;
                if (model.is_default) {
                    displayName += ' ⭐ (Anbefalt)';
                }
                if (model.cost === 'svært lav') {
                    displayName += ' (Billig)';
                } else if (model.cost === 'høy' || model.cost === 'svært høy') {
                    displayName += ' (Dyr)';
                }
                
                option.textContent = displayName;
                select.appendChild(option);
            });
            
            console.log('Loaded ' + data.models.length + ' models from API');
        }
    } catch (error) {
        console.warn('Kunne ikke laste modeller fra API, bruker HTML-defaults:', error);
        // Behold modeller som er hardkodet i HTML
    }
}

function loadFallbackModels() {
    // Fallback hvis API feiler
    const select = document.getElementById('model-select');
    if (!select) return;
    
    select.innerHTML = '';
    const fallbackModels = [
        {id: 'gpt-4-turbo-2024-04-09', name: 'GPT-4.1 Mini ⭐'},
        {id: 'gpt-4', name: 'GPT-4'},
        {id: 'gpt-4-turbo', name: 'GPT-4.1 Turbo'},
        {id: 'gpt-4o-mini', name: 'GPT-4o Mini'},
        {id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo'}
    ];
    
    fallbackModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model.id;
        option.textContent = model.name;
        select.appendChild(option);
    });
    
    console.log('Loaded fallback models');
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

// ==================== MEMORY FUNCTIONS ====================

let memoryViewVisible = false;
let factsViewMode = 'list'; // 'list' or 'category'

async function loadMemoryStats() {
    try {
        const response = await fetch('/api/memory/stats');
        const data = await response.json();
        
        if (data.status === 'success') {
            document.getElementById('memory-stats-facts').textContent = data.stats.total_facts;
            document.getElementById('memory-stats-memories').textContent = data.stats.total_memories;
            document.getElementById('memory-stats-messages').textContent = data.stats.total_messages;
        }
    } catch (error) {
        console.error('Memory stats error:', error);
    }
    
    // Load quick facts
    loadQuickFacts();
    
    // Load embedding status
    loadEmbeddingStatus();
    
    // Load worker status
    loadWorkerStatus();
}

async function loadQuickFacts() {
    try {
        const response = await fetch('/api/memory/quick-facts');
        const data = await response.json();
        
        if (data.status === 'success' && data.facts) {
            const content = document.getElementById('quick-facts-content');
            
            // Parse facts array into structured data
            const factMap = {};
            data.facts.forEach(f => {
                factMap[f.key] = f.value;
            });
            
            let html = '';
            
            // Name
            if (factMap.user_name) {
                html += '<p style="margin: 5px 0;"><strong>Navn:</strong> ' + factMap.user_name + '</p>';
            }
            
            // Sisters
            const sisters = [];
            for (let i = 1; i <= 10; i++) {
                if (factMap['sister_' + i + '_name']) {
                    sisters.push(factMap['sister_' + i + '_name']);
                }
            }
            if (sisters.length > 0) {
                html += '<p style="margin: 5px 0;"><strong>Søstre:</strong> ' + sisters.join(', ') + ' (' + sisters.length + ')</p>';
            }
            
            // Show top facts if we have them
            if (html === '' && data.facts.length > 0) {
                html = '<p style="margin: 5px 0; font-size: 12px; color: #666;">Topp fakta:</p>';
                data.facts.slice(0, 5).forEach(f => {
                    const keyDisplay = f.key.replace(/_/g, ' ');
                    html += '<p style="margin: 3px 0; font-size: 11px;">• <strong>' + keyDisplay + ':</strong> ' + f.value + '</p>';
                });
            }
            
            content.innerHTML = html || '<p style="color: #999;">Ingen fakta ennå</p>';
        }
    } catch (error) {
        console.error('Quick facts error:', error);
        document.getElementById('quick-facts-content').innerHTML = '<p style="color: #999;">Kunne ikke laste nøkkelfakta</p>';
    }
}

async function loadEmbeddingStatus() {
    try {
        const response = await fetch('/api/memory/embedding-status');
        const data = await response.json();
        
        if (data.status === 'success') {
            const statusText = document.getElementById('embedding-status-text');
            const withEmbeddings = data.with_embeddings || data.with_embedding || 0;
            const totalFacts = data.total_memories || data.total_facts || 0;
            const percentage = Math.round(data.percentage || 0);
            const emoji = percentage === 100 ? '✅' : percentage >= 80 ? '⚠️' : '❌';
            statusText.textContent = emoji + ' Embeddings: ' + withEmbeddings + '/' + totalFacts + ' (' + percentage + '%)';
        }
    } catch (error) {
        console.error('Embedding status error:', error);
    }
}

async function loadWorkerStatus() {
    try {
        const response = await fetch('/api/memory/worker-status');
        const data = await response.json();
        
        if (data.status === 'success') {
            const content = document.getElementById('worker-status-content');
            const statusEmoji = data.running ? '🟢' : '🔴';
            const statusText = data.running ? 'Aktiv' : 'Inaktiv';
            
            let html = '<p style="margin: 5px 0;">' + statusEmoji + ' <strong>Status:</strong> ' + statusText + '</p>';
            html += '<p style="margin: 5px 0;"><strong>Uprosesserte:</strong> ' + (data.unprocessed || 0) + ' meldinger</p>';
            
            if (data.last_processed) {
                const date = new Date(data.last_processed);
                const timeStr = date.toLocaleString('no-NO');
                html += '<p style="margin: 5px 0; font-size: 12px; color: #666;"><strong>Sist:</strong> ' + timeStr + '</p>';
            }
            
            content.innerHTML = html;
        }
    } catch (error) {
        console.error('Worker status error:', error);
        document.getElementById('worker-status-content').innerHTML = '<p style="color: #999;">Kunne ikke hente status</p>';
    }
}

async function toggleMemoryView() {
    const view = document.getElementById('memory-view');
    const toggleText = document.getElementById('memory-toggle-text');
    
    memoryViewVisible = !memoryViewVisible;
    
    if (memoryViewVisible) {
        view.style.display = 'block';
        toggleText.textContent = '🙈 Skjul detaljert minne';
        await loadRecentUpdates();
        await loadMemoryFacts();
        await loadMemoryMemories();
        await loadMemoryTopics();
    } else {
        view.style.display = 'none';
        toggleText.textContent = '👁️ Vis detaljert minne';
    }
}

async function loadRecentUpdates() {
    const list = document.getElementById('recent-updates-list');
    list.innerHTML = '<p style="color: #999; text-align: center;">Laster...</p>';
    
    try {
        const response = await fetch('/api/memory/recent-updates');
        const data = await response.json();
        
        if (data.status === 'success' && data.updates.length > 0) {
            let html = '<div style="display: flex; flex-direction: column; gap: 8px;">';
            
            data.updates.forEach(update => {
                const date = new Date(update.first_seen);
                const timeStr = date.toLocaleTimeString('no-NO', {hour: '2-digit', minute: '2-digit'});
                const dateStr = date.toLocaleDateString('no-NO', {day: '2-digit', month: '2-digit'});
                
                html += '<div style="padding: 8px; background: #f5f5f5; border-radius: 6px; border-left: 3px solid #ff9800;">';
                html += '<div style="font-size: 13px; color: #333;">' + update.text + '</div>';
                html += '<div style="font-size: 11px; color: #999; margin-top: 4px;">📅 ' + dateStr + ' ' + timeStr;
                if (update.topic) html += ' • ' + update.topic;
                html += ' • Confidence: ' + Math.round(update.confidence * 100) + '%';
                html += '</div></div>';
            });
            
            html += '</div>';
            list.innerHTML = html;
        } else {
            list.innerHTML = '<p style="color: #999; text-align: center;">Ingen oppdateringer</p>';
        }
    } catch (error) {
        list.innerHTML = '<p style="color: #f44336;">Feil ved lasting</p>';
        console.error('Recent updates error:', error);
    }
}

function toggleFactsView() {
    factsViewMode = factsViewMode === 'list' ? 'category' : 'list';
    const button = document.getElementById('facts-view-toggle');
    button.textContent = factsViewMode === 'list' ? '📁 Vis etter kategori' : '📄 Vis som liste';
    
    if (window.memoryFacts) {
        displayFacts(window.memoryFacts);
    }
}

async function loadMemoryFacts() {
    const list = document.getElementById('memory-facts-list');
    list.innerHTML = '<p style="color: #999; text-align: center;">Laster fakta...</p>';
    
    try {
        const response = await fetch('/api/memory/profile');
        const data = await response.json();
        
        if (data.status === 'success' && data.facts.length > 0) {
            // Lagre facts globalt for filtrering
            window.memoryFacts = data.facts;
            displayFacts(data.facts);
        } else {
            list.innerHTML = '<p style="color: #999; text-align: center;">Ingen fakta lagret ennå</p>';
        }
    } catch (error) {
        list.innerHTML = '<p style="color: #f44336;">Feil ved lasting av fakta</p>';
        console.error('Memory facts error:', error);
    }
}

function displayFacts(facts) {
    const list = document.getElementById('memory-facts-list');
    if (facts.length === 0) {
        list.innerHTML = '<p style="color: #999; text-align: center;">Ingen treff</p>';
        return;
    }
    
    if (factsViewMode === 'category') {
        // Group by topic
        const grouped = {};
        facts.forEach(fact => {
            if (!grouped[fact.topic]) {
                grouped[fact.topic] = [];
            }
            grouped[fact.topic].push(fact);
        });
        
        let html = '';
        Object.keys(grouped).sort().forEach(topic => {
            const topicFacts = grouped[topic];
            const topicColors = {
                'family': '#e91e63',
                'identity': '#9c27b0',
                'preferences': '#ff5722',
                'work': '#3f51b5',
                'projects': '#00bcd4',
                'technical': '#009688',
                'health': '#4caf50',
                'pets': '#ff9800',
                'hobby': '#795548'
            };
            const color = topicColors[topic] || '#757575';
            
            html += '<div style="margin-bottom: 15px;">';
            html += '<div style="font-weight: bold; color: ' + color + '; margin-bottom: 8px; padding: 6px 10px; background: rgba(0,0,0,0.05); border-radius: 6px;">📁 ' + topic + ' (' + topicFacts.length + ')</div>';
            
            topicFacts.forEach(fact => {
                const confidenceColor = fact.confidence >= 0.8 ? '#4caf50' : fact.confidence >= 0.5 ? '#ff9800' : '#f44336';
                html += '<div style="padding: 10px; margin-bottom: 8px; margin-left: 15px; background: #f5f5f5; border-radius: 8px; border-left: 4px solid ' + confidenceColor + ';">';
                html += '<div style="font-weight: bold; color: #333; margin-bottom: 5px; word-wrap: break-word;">' + fact.key + '</div>';
                html += '<div style="color: #666; word-wrap: break-word; margin-bottom: 8px;">' + fact.value + '</div>';
                html += '<div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #999;">';
                html += '<span style="white-space: nowrap;">📊 ' + (fact.confidence * 100).toFixed(0) + '%</span>';
                html += '<span>|</span>';
                html += '<span style="white-space: nowrap;">🔢 ' + fact.frequency + 'x</span>';
                html += '<button onclick="deleteFact(\'' + fact.key + '\')" style="margin-left: auto !important; flex-shrink: 0 !important; background: transparent !important; color: #f44336 !important; border: none !important; padding: 0 !important; cursor: pointer; font-size: 16px !important; line-height: 1 !important; width: auto !important; min-width: 0 !important; transition: all 0.2s;" onmouseover="this.style.color=\'#c62828\'" onmouseout="this.style.color=\'#f44336\'" title="Slett">🗑️</button>';
                html += '</div></div>';
            });
            
            html += '</div>';
        });
        
        list.innerHTML = html;
    } else {
        // List view
        let html = '';
        facts.forEach(fact => {
            const confidenceColor = fact.confidence >= 0.8 ? '#4caf50' : fact.confidence >= 0.5 ? '#ff9800' : '#f44336';
            html += '<div style="padding: 10px; margin-bottom: 8px; background: #f5f5f5; border-radius: 8px; border-left: 4px solid ' + confidenceColor + ';">';
            html += '<div style="font-weight: bold; color: #333; margin-bottom: 5px; word-wrap: break-word;">' + fact.key + '</div>';
            html += '<div style="color: #666; word-wrap: break-word; margin-bottom: 8px;">' + fact.value + '</div>';
            html += '<div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #999;">';
            html += '<span style="white-space: nowrap;">📊 ' + (fact.confidence * 100).toFixed(0) + '%</span>';
            html += '<span>|</span>';
            html += '<span style="white-space: nowrap;">🔢 ' + fact.frequency + 'x</span>';
            html += '<span>|</span>';
            html += '<span style="white-space: nowrap;">🏷️ ' + fact.topic + '</span>';
            html += '<button onclick="deleteFact(\'' + fact.key + '\')" style="margin-left: auto !important; flex-shrink: 0 !important; background: transparent !important; color: #f44336 !important; border: none !important; padding: 0 !important; cursor: pointer; font-size: 16px !important; line-height: 1 !important; width: auto !important; min-width: 0 !important; transition: all 0.2s;" onmouseover="this.style.color=\'#c62828\'" onmouseout="this.style.color=\'#f44336\'" title="Slett">🗑️</button>';
            html += '</div></div>';
        });
        list.innerHTML = html;
    }
}

function filterFacts() {
    const searchInput = document.getElementById('facts-search');
    const searchTerm = searchInput.value.toLowerCase();
    
    if (!window.memoryFacts) {
        return;
    }
    
    if (searchTerm === '') {
        displayFacts(window.memoryFacts);
        return;
    }
    
    const filtered = window.memoryFacts.filter(fact => 
        fact.key.toLowerCase().includes(searchTerm) ||
        fact.value.toLowerCase().includes(searchTerm) ||
        fact.topic.toLowerCase().includes(searchTerm)
    );
    
    displayFacts(filtered);
}

async function loadMemoryMemories(query = '') {
    const list = document.getElementById('memory-memories-list');
    list.innerHTML = '<p style="color: #999; text-align: center;">Laster minner...</p>';
    
    try {
        const url = '/api/memory/memories';
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'success' && data.memories.length > 0) {
            // Lagre i global variabel for filtrering
            window.memoryMemories = data.memories;
            displayMemories(data.memories);
        } else {
            window.memoryMemories = [];
            list.innerHTML = '<p style="color: #999; text-align: center;">Ingen minner funnet</p>';
        }
    } catch (error) {
        window.memoryMemories = [];
        list.innerHTML = '<p style="color: #f44336;">Feil ved lasting av minner</p>';
        console.error('Memory memories error:', error);
    }
}

function displayMemories(memories) {
    const list = document.getElementById('memory-memories-list');
    
    if (!memories || memories.length === 0) {
        list.innerHTML = '<p style="color: #999; text-align: center;">Ingen minner funnet</p>';
        return;
    }
    
    let html = '';
    memories.forEach(mem => {
        const topicColors = {
            'family': '#e91e63',
            'hobby': '#9c27b0',
            'work': '#3f51b5',
            'projects': '#00bcd4',
            'technical': '#009688',
            'health': '#4caf50',
            'pets': '#ff9800',
            'preferences': '#ff5722'
        };
        const topicColor = topicColors[mem.topic] || '#757575';
        
        const scoreHtml = mem.score ? `<span>|</span><span style="white-space: nowrap;">⭐ ${mem.score.toFixed(2)}</span>` : '';
        html += `
            <div style="padding: 10px; margin-bottom: 8px; background: #f5f5f5; border-radius: 8px; border-left: 4px solid ${topicColor};">
                <div style="color: #333; margin-bottom: 8px; word-wrap: break-word;">${mem.text}</div>
                <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #999;">
                    <span style="white-space: nowrap;">🏷️ ${mem.topic}</span>
                    <span>|</span>
                    <span style="white-space: nowrap;">🔢 ${mem.frequency}x</span>
                    <span>|</span>
                    <span style="white-space: nowrap;">📅 ${new Date(mem.last_accessed).toLocaleDateString('nb-NO')}</span>
                    ${scoreHtml}
                    <button onclick="deleteMemory(${mem.id})" style="margin-left: auto !important; flex-shrink: 0 !important; background: transparent !important; color: #f44336 !important; border: none !important; padding: 0 !important; cursor: pointer; font-size: 16px !important; line-height: 1 !important; width: auto !important; min-width: 0 !important; transition: all 0.2s;" onmouseover="this.style.color='#c62828'" onmouseout="this.style.color='#f44336'" title="Slett">🗑️</button>
                </div>
            </div>
        `;
    });
    list.innerHTML = html;
}

function filterMemories() {
    const searchInput = document.getElementById('memory-search');
    const searchTerm = searchInput.value.toLowerCase();
    
    if (!window.memoryMemories) {
        return;
    }
    
    if (searchTerm === '') {
        displayMemories(window.memoryMemories);
        return;
    }
    
    const filtered = window.memoryMemories.filter(memory => 
        memory.text.toLowerCase().includes(searchTerm) ||
        memory.topic.toLowerCase().includes(searchTerm)
    );
    
    displayMemories(filtered);
}

async function loadMemoryTopics() {
    const list = document.getElementById('memory-topics-list');
    list.innerHTML = '<p style="color: #999; text-align: center;">Laster emner...</p>';
    
    try {
        const response = await fetch('/api/memory/topics');
        const data = await response.json();
        
        if (data.status === 'success' && data.topics.length > 0) {
            const total = data.topics.reduce((sum, t) => sum + t.mention_count, 0);
            
            let html = '';
            data.topics.forEach(topic => {
                const percentage = (topic.mention_count / total * 100).toFixed(1);
                const barWidth = Math.min(percentage, 100);
                
                const topicEmojis = {
                    'family': '👨‍👩‍👧‍👦',
                    'hobby': '🎨',
                    'work': '💼',
                    'projects': '🚀',
                    'technical': '💻',
                    'health': '❤️',
                    'pets': '🐾',
                    'preferences': '⭐',
                    'weather': '🌤️',
                    'general': '💬'
                };
                const emoji = topicEmojis[topic.topic] || '📌';
                
                html += `
                    <div style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 14px;">
                            <span>${emoji} ${topic.topic}</span>
                            <span style="color: #666;">${topic.mention_count} (${percentage}%)</span>
                        </div>
                        <div style="width: 100%; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden;">
                            <div style="width: ${barWidth}%; height: 100%; background: linear-gradient(90deg, #00bcd4, #009688); transition: width 0.3s;"></div>
                        </div>
                    </div>
                `;
            });
            list.innerHTML = html;
        } else {
            list.innerHTML = '<p style="color: #999; text-align: center;">Ingen emner ennå</p>';
        }
    } catch (error) {
        list.innerHTML = '<p style="color: #f44336;">Feil ved lasting av emner</p>';
        console.error('Memory topics error:', error);
    }
}

async function deleteFact(key) {
    if (!confirm(`Er du sikker på at du vil slette "${key}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/memory/profile/${encodeURIComponent(key)}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✅ ' + data.message);
            await loadMemoryFacts();
            await loadMemoryStats();
        } else {
            alert('❌ Feil: ' + data.message);
        }
    } catch (error) {
        alert('❌ Feil ved sletting: ' + error.message);
        console.error('Delete fact error:', error);
    }
}

async function deleteMemory(id) {
    if (!confirm(`Er du sikker på at du vil slette dette minnet?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/memory/memories/${id}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✅ ' + data.message);
            await loadMemoryMemories();
            await loadMemoryStats();
        } else {
            alert('❌ Feil: ' + data.message);
        }
    } catch (error) {
        alert('❌ Feil ved sletting: ' + error.message);
        console.error('Delete memory error:', error);
    }
}

// User Management Functions
function toggleUserPanel() {
    const panel = document.getElementById('user-panel');
    const button = document.querySelector('.btn-user');
    
    if (panel.style.display === 'none' || !panel.style.display) {
        panel.style.display = 'block';
        button.textContent = '👥 Skjul Brukerpanel';
        loadUsers();  // Last brukere når panelet åpnes
    } else {
        panel.style.display = 'none';
        button.textContent = '👥 Bytt Bruker';
    }
}

async function loadCurrentUser() {
    try {
        const response = await fetch('/api/users/current');
        const data = await response.json();
        
        document.getElementById('user-name').textContent = data.display_name;
        document.getElementById('user-relation').textContent = 
            data.username !== 'Osmund' ? `(${data.relation})` : '';
    } catch (error) {
        console.error('Kunne ikke laste current user:', error);
        document.getElementById('user-name').textContent = 'Ukjent';
    }
}

async function loadUsers() {
    try {
        const response = await fetch('/api/users/list');
        const data = await response.json();
        
        // Oppdater dropdown
        const select = document.getElementById('user-select');
        select.innerHTML = '<option value="">-- Velg bruker --</option>';
        data.users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.username;
            option.textContent = `${user.display_name} (${user.relation})`;
            select.appendChild(option);
        });
        
        // Oppdater liste
        const listDiv = document.getElementById('users-list');
        listDiv.innerHTML = '';
        
        data.users.forEach(user => {
            const userDiv = document.createElement('div');
            userDiv.style.cssText = 'padding: 10px; margin: 5px 0; background: white; border-radius: 5px; border-left: 4px solid #667eea;';
            
            const isCurrent = user.username === data.current_user;
            const badge = isCurrent ? '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.8em; margin-left: 5px;">Aktiv</span>' : '';
            
            userDiv.innerHTML = `
                <div style="font-weight: bold; color: #333;">
                    👤 ${user.display_name} ${badge}
                </div>
                <div style="font-size: 0.9em; color: #666; margin-top: 3px;">
                    ${user.relation} • ${user.total_messages} meldinger
                </div>
                <div style="font-size: 0.8em; color: #999; margin-top: 3px;">
                    Sist aktiv: ${formatTimestamp(user.last_active)}
                </div>
            `;
            
            listDiv.appendChild(userDiv);
        });
    } catch (error) {
        console.error('Kunne ikke laste brukere:', error);
        document.getElementById('users-list').innerHTML = '<div style="color: red;">Feil ved lasting av brukere</div>';
    }
}

async function switchToUser() {
    const select = document.getElementById('user-select');
    const username = select.value;
    
    if (!username) {
        alert('Velg en bruker først');
        return;
    }
    
    try {
        const response = await fetch('/api/users/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username })
        });
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Byttet til ${data.display_name}`);
            loadCurrentUser();
            loadUsers();
        } else {
            alert('❌ Feil: ' + (data.error || 'Kunne ikke bytte bruker'));
        }
    } catch (error) {
        alert('❌ Feil: ' + error.message);
    }
}

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Nå';
    if (diffMins < 60) return `${diffMins} min siden`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)} timer siden`;
    return `${Math.floor(diffMins / 1440)} dager siden`;
}

// Load current settings on page load
window.onload = function() {
    updateStatus();
    loadCurrentUser();  // Last current user
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
    loadMemoryStats();  // Last memory stats
    loadMaxContextFacts();  // Last max context facts setting
    loadMemorySettings();  // Last alle memory settings
    loadBoredomStatus();  // Last kjedsomhetsnivå
    loadHungerStatus();  // Last hunger nivå
    loadVisionStatus();  // Last Duck-Vision status
    updateSleepModeStatus();  // Last sleep mode status
    loadSMSHistory();  // Last SMS historikk
    loadContacts();  // Last SMS kontakter
    loadDuckLocation();  // Last Andas lokasjon
    loadSystemStats();  // Last system stats (CPU temp, minne)
    
    // Oppdater status automatisk hvert 5. sekund
    setInterval(updateStatus, 5000);
    setInterval(loadCurrentUser, 10000);  // Oppdater current user hvert 10. sekund
    setInterval(loadFanStatus, 5000);
    setInterval(loadMemoryStats, 10000);  // Oppdater memory stats hvert 10. sekund
    setInterval(loadBoredomStatus, 5000);  // Oppdater kjedsomhet hvert 5. sekund
    setInterval(loadHungerStatus, 5000);  // Oppdater hunger hvert 5. sekund
    setInterval(loadVisionStatus, 5000);  // Oppdater Duck-Vision status hvert 5. sekund
    setInterval(updateSleepModeStatus, 1000);  // Oppdater sleep mode hvert sekund (rask respons)
    setInterval(loadContacts, 10000);  // Oppdater kontakter hvert 10. sekund
    setInterval(loadSMSHistory, 10000);  // Oppdater SMS historikk hvert 10. sekund
    setInterval(loadDuckLocation, 10000);  // Oppdater Andas lokasjon hvert 10. sekund
    setInterval(loadPrinterStatus, 10000);  // Oppdater 3D printer status hvert 10. sekund
    setInterval(loadSystemStats, 5000);  // Oppdater system stats hvert 5. sekund
};

// Boredom Status
async function loadBoredomStatus() {
    try {
        const response = await fetch('/boredom-status');
        const data = await response.json();
        
        document.getElementById('boredom-emoji').textContent = data.emoji;
        document.getElementById('boredom-level').textContent = data.level;
        document.getElementById('boredom-status').textContent = data.status;
        
        const bar = document.getElementById('boredom-bar');
        bar.style.width = (data.level * 10) + '%';
        bar.style.background = data.color;
    } catch (error) {
        console.error('Kunne ikke laste kjedsomhetsnivå:', error);
    }
}

// Duck Location
async function loadDuckLocation() {
    try {
        const response = await fetch('/duck_location');
        const data = await response.json();
        
        const locationText = document.getElementById('duck-location-text');
        if (data.location && data.location !== 'Ukjent') {
            locationText.textContent = data.location;
            locationText.style.color = '#667eea';
        } else {
            locationText.textContent = 'Ukjent';
            locationText.style.color = '#999';
        }
    } catch (error) {
        console.error('Kunne ikke laste Andas lokasjon:', error);
        document.getElementById('duck-location-text').textContent = 'Feil';
    }
}

// Duck-Vision Status
async function loadVisionStatus() {
    try {
        const response = await fetch('/vision-status');
        const data = await response.json();
        
        const statusText = document.getElementById('vision-status-text');
        if (data.connected) {
            statusText.textContent = '✅ Tilkoblet';
            statusText.style.color = '#10b981';  // grønn
        } else {
            statusText.textContent = '❌ Ikke tilkoblet';
            statusText.style.color = '#ef4444';  // rød
        }
    } catch (error) {
        console.error('Kunne ikke laste Duck-Vision status:', error);
        document.getElementById('vision-status-text').textContent = '❓ Feil';
    }
}

// Hunger Status (Tamagotchi!)
async function loadHungerStatus() {
    try {
        const response = await fetch('/hunger-status');
        const data = await response.json();
        
        document.getElementById('hunger-emoji').textContent = data.emoji;
        document.getElementById('hunger-level').textContent = data.level;
        document.getElementById('hunger-status').textContent = data.status;
        document.getElementById('meals-today').textContent = data.meals_today || 0;
        document.getElementById('next-meal').textContent = data.next_meal_time || '12:00';
        
        const bar = document.getElementById('hunger-bar');
        bar.style.width = (data.level * 10) + '%';
        bar.style.background = data.color;
    } catch (error) {
        console.error('Kunne ikke laste hunger nivå:', error);
    }
}

// Feed Anda from control panel
async function feedAnda(foodType) {
    const statusElement = document.getElementById('feed-status');
    const foodEmoji = foodType === 'cookie' ? '🍪' : '🍕';
    
    try {
        statusElement.textContent = `Gir ${foodEmoji}...`;
        
        const response = await fetch('/api/hunger/feed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ food_type: foodType })
        });
        const data = await response.json();
        
        if (data.status === 'fed') {
            statusElement.textContent = `✅ ${data.food} Nam nam! Hunger: ${data.new_level}/10`;
            // Refresh hunger status
            setTimeout(() => {
                loadHungerStatus();
                statusElement.textContent = '';
            }, 2000);
        } else {
            statusElement.textContent = `❌ Feil: ${data.message || 'Ukjent feil'}`;
        }
    } catch (error) {
        statusElement.textContent = `❌ Feil: ${error.message}`;
    }
}

// 3D Printer Status
async function loadPrinterStatus() {
    try {
        const response = await fetch('/api/printer/status');
        const data = await response.json();
        
        const loadingEl = document.getElementById('printer-loading');
        const statusEl = document.getElementById('printer-status');
        const errorEl = document.getElementById('printer-error');
        
        // Hide loading
        loadingEl.style.display = 'none';
        
        if (data.status === 'not_configured') {
            errorEl.style.display = 'block';
            statusEl.style.display = 'none';
            document.getElementById('printer-error-text').textContent = 'PrusaLink ikke konfigurert';
            return;
        }
        
        if (data.status === 'error') {
            errorEl.style.display = 'block';
            statusEl.style.display = 'none';
            document.getElementById('printer-error-text').textContent = data.message || 'Ukjent feil';
            return;
        }
        
        // Show printer status
        errorEl.style.display = 'none';
        statusEl.style.display = 'block';
        
        const printer = data.printer;
        const state = printer.state;
        
        // Update emoji based on state
        const emojiMap = {
            'IDLE': '🛌',
            'PRINTING': '🖨️',
            'PAUSED': '⏸️',
            'FINISHED': '✅',
            'STOPPED': '🛑',
            'ERROR': '❌'
        };
        document.getElementById('printer-emoji').textContent = emojiMap[state] || '🖨️';
        
        // Update state text
        const stateTextMap = {
            'IDLE': 'Klar',
            'PRINTING': 'Printer...',
            'PAUSED': 'Pause',
            'FINISHED': 'Ferdig!',
            'STOPPED': 'Stoppet',
            'ERROR': 'Feil'
        };
        document.getElementById('printer-state-text').textContent = stateTextMap[state] || state;
        
        // Show/hide progress bar
        const progressContainer = document.getElementById('printer-progress-container');
        if (state === 'PRINTING' || state === 'PAUSED') {
            progressContainer.style.display = 'block';
            document.getElementById('printer-job-name').textContent = printer.job_name;
            
            const progress = Math.round(printer.progress);
            const progressBar = document.getElementById('printer-progress-bar');
            const progressText = document.getElementById('printer-progress-text');
            
            progressBar.style.width = progress + '%';
            progressText.textContent = progress + '%';
            
            // Time remaining
            if (printer.time_remaining) {
                const hours = Math.floor(printer.time_remaining / 3600);
                const minutes = Math.floor((printer.time_remaining % 3600) / 60);
                let timeText = '';
                if (hours > 0) {
                    timeText = `${hours}t ${minutes}m igjen`;
                } else {
                    timeText = `${minutes}m igjen`;
                }
                document.getElementById('printer-time-remaining').textContent = timeText;
            } else {
                document.getElementById('printer-time-remaining').textContent = 'Beregner...';
            }
        } else {
            progressContainer.style.display = 'none';
        }
        
        // Update temperatures
        if (printer.temp_nozzle) {
            document.getElementById('printer-temp-nozzle').textContent = Math.round(printer.temp_nozzle);
        }
        if (printer.temp_bed) {
            document.getElementById('printer-temp-bed').textContent = Math.round(printer.temp_bed);
        }
        
        // Update human readable message
        document.getElementById('printer-message').textContent = data.human_readable || '';
        
    } catch (error) {
        console.error('Failed to load printer status:', error);
        document.getElementById('printer-loading').style.display = 'none';
        document.getElementById('printer-error').style.display = 'block';
        document.getElementById('printer-error-text').textContent = 'Kunne ikke hente status: ' + error.message;
    }
}

// Max Context Facts
function updateMaxFactsLabel() {
    const slider = document.getElementById('max-facts-slider');
    const label = document.getElementById('max-facts-label');
    label.textContent = slider.value + ' fakta';
}

async function changeMaxFacts() {
    const slider = document.getElementById('max-facts-slider');
    const statusElement = document.getElementById('max-facts-status');
    const value = parseInt(slider.value);
    
    try {
        const response = await fetch('/api/settings/max-context-facts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_context_facts: value })
        });
        const data = await response.json();
        
        if (data.success) {
            statusElement.textContent = ' ✓';
            setTimeout(() => statusElement.textContent = '', 2000);
        } else {
            statusElement.textContent = ' ✗ Feil: ' + (data.error || 'Ukjent feil');
        }
    } catch (error) {
        statusElement.textContent = ' ✗ Feil: ' + error.message;
    }
}

async function loadMaxContextFacts() {
    try {
        const response = await fetch('/api/settings/max-context-facts');
        const data = await response.json();
        if (data.status === 'success') {
            const slider = document.getElementById('max-facts-slider');
            slider.value = data.max_context_facts;
            updateMaxFactsLabel();
        }
    } catch (error) {
        console.error('Kunne ikke laste max context facts:', error);
    }
}

async function loadMemorySettings() {
    try {
        const response = await fetch('/api/settings/memory');
        const data = await response.json();
        if (data.status === 'success') {
            // Embedding search limit
            const embeddingSlider = document.getElementById('embedding-limit-slider');
            if (embeddingSlider) {
                embeddingSlider.value = data.embedding_search_limit || 30;
                updateEmbeddingLimitLabel();
            }
            
            // Memory limit
            const memorySlider = document.getElementById('memory-limit-slider');
            if (memorySlider) {
                memorySlider.value = data.memory_limit || 8;
                updateMemoryLimitLabel();
            }
            
            // Memory threshold (konverter fra 0.35 til 35 for slider)
            const thresholdSlider = document.getElementById('memory-threshold-slider');
            if (thresholdSlider) {
                thresholdSlider.value = Math.round((data.memory_threshold || 0.35) * 100);
                updateMemoryThresholdLabel();
            }
        }
    } catch (error) {
        console.error('Kunne ikke laste memory settings:', error);
    }
}

function updateEmbeddingLimitLabel() {
    const slider = document.getElementById('embedding-limit-slider');
    const label = document.getElementById('embedding-limit-value');
    if (slider && label) {
        label.textContent = slider.value;
    }
}

async function changeEmbeddingLimit() {
    const slider = document.getElementById('embedding-limit-slider');
    const statusElement = document.getElementById('embedding-limit-status');
    
    try {
        const response = await fetch('/api/settings/memory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ embedding_search_limit: parseInt(slider.value) })
        });
        
        const data = await response.json();
        if (data.success) {
            statusElement.textContent = ' ✓';
            setTimeout(() => { statusElement.textContent = ''; }, 2000);
        } else {
            statusElement.textContent = ' ✗ ' + (data.error || 'Feil');
        }
    } catch (error) {
        statusElement.textContent = ' ✗ ' + error.message;
    }
}

function updateMemoryLimitLabel() {
    const slider = document.getElementById('memory-limit-slider');
    const label = document.getElementById('memory-limit-value');
    if (slider && label) {
        label.textContent = slider.value;
    }
}

async function changeMemoryLimit() {
    const slider = document.getElementById('memory-limit-slider');
    const statusElement = document.getElementById('memory-limit-status');
    
    try {
        const response = await fetch('/api/settings/memory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ memory_limit: parseInt(slider.value) })
        });
        
        const data = await response.json();
        if (data.success) {
            statusElement.textContent = ' ✓';
            setTimeout(() => { statusElement.textContent = ''; }, 2000);
        } else {
            statusElement.textContent = ' ✗ ' + (data.error || 'Feil');
        }
    } catch (error) {
        statusElement.textContent = ' ✗ ' + error.message;
    }
}

function updateMemoryThresholdLabel() {
    const slider = document.getElementById('memory-threshold-slider');
    const label = document.getElementById('memory-threshold-value');
    if (slider && label) {
        // Konverter fra 20-80 (slider) til 0.20-0.80 (display)
        const val = (parseInt(slider.value) / 100).toFixed(2);
        label.textContent = val;
    }
}

async function changeMemoryThreshold() {
    const slider = document.getElementById('memory-threshold-slider');
    const statusElement = document.getElementById('memory-threshold-status');
    
    try {
        // Konverter fra 20-80 (slider) til 0.20-0.80 (backend)
        const threshold = parseInt(slider.value) / 100;
        
        const response = await fetch('/api/settings/memory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ memory_threshold: threshold })
        });
        
        const data = await response.json();
        if (data.success) {
            statusElement.textContent = ' ✓';
            setTimeout(() => { statusElement.textContent = ''; }, 2000);
        } else {
            statusElement.textContent = ' ✗ ' + (data.error || 'Feil');
        }
    } catch (error) {
        statusElement.textContent = ' ✗ ' + error.message;
    }
}

// Sleep Mode Functions
async function updateSleepModeStatus() {
    try {
        const response = await fetch('/sleep_status');
        const data = await response.json();
        
        const statusDiv = document.getElementById('sleep-mode-status');
        const toggleBtn = document.getElementById('sleep-toggle-btn');
        const countdownDiv = document.getElementById('sleep-countdown');
        const endTimeSpan = document.getElementById('sleep-end-time');
        const remainingSpan = document.getElementById('sleep-remaining');
        
        if (data.is_sleeping) {
            statusDiv.textContent = '💤 Anda sover';
            statusDiv.style.color = '#1565c0';
            toggleBtn.textContent = '⏰ Våkn opp';
            toggleBtn.style.background = '#ff9800';
            countdownDiv.style.display = 'block';
            endTimeSpan.textContent = data.end_time_formatted || '';
            remainingSpan.textContent = data.remaining_minutes || 0;
        } else {
            statusDiv.textContent = '✅ Anda er våken';
            statusDiv.style.color = '#4caf50';
            toggleBtn.textContent = '💤 Aktiver søvn';
            toggleBtn.style.background = '#42a5f5';
            countdownDiv.style.display = 'none';
        }
    } catch (error) {
        console.error('Feil ved henting av sleep mode status:', error);
    }
}

async function toggleSleepMode() {
    const statusDiv = document.getElementById('sleep-mode-status');
    
    try {
        // Sjekk nåværende status
        const statusResponse = await fetch('/sleep_status');
        const statusData = await statusResponse.json();
        
        if (statusData.is_sleeping) {
            // Deaktiver sleep mode
            const response = await fetch('/sleep/disable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            if (data.success) {
                await updateSleepModeStatus();
            } else {
                alert('Feil ved deaktivering av sleep mode: ' + (data.error || 'Ukjent feil'));
            }
        } else {
            // Aktiver sleep mode
            const durationSelect = document.getElementById('sleep-duration');
            const durationMinutes = parseInt(durationSelect.value);
            
            const response = await fetch('/sleep/enable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ duration_minutes: durationMinutes })
            });
            
            const data = await response.json();
            if (data.success) {
                await updateSleepModeStatus();
            } else {
                alert('Feil ved aktivering av sleep mode: ' + (data.error || 'Ukjent feil'));
            }
        }
    } catch (error) {
        alert('Nettverksfeil: ' + error.message);
    }
}
// === SMS History Functions ===
async function loadSMSHistory() {
    try {
        const response = await fetch('/sms_history');
        if (!response.ok) {
            throw new Error('Kunne ikke laste SMS-historikk');
        }
        
        const smsList = await response.json();
        const container = document.getElementById('sms-history-container');
        
        if (smsList.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">Ingen SMS ennå</div>';
            return;
        }
        
        let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';
        
        smsList.forEach(sms => {
            const isIncoming = sms.direction === 'inbound';
            const isDuckMessage = sms.message_type === 'duck';
            
            // Different styling for duck messages
            const bgColor = isDuckMessage ? (isIncoming ? '#fff3e0' : '#ffe0b2') : (isIncoming ? '#e3f2fd' : '#f1f8e9');
            const borderColor = isDuckMessage ? '#ff9800' : (isIncoming ? '#42a5f5' : '#66bb6a');
            const icon = isDuckMessage ? '🦆' : (isIncoming ? '📩' : '📤');
            const directionText = isIncoming ? 'Fra' : 'Til';
            
            // Format timestamp
            const date = new Date(sms.timestamp);
            const timeStr = date.toLocaleString('nb-NO', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            html += `
                <div style="padding: 10px; background: ${bgColor}; border-left: 4px solid ${borderColor}; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <strong>${icon} ${directionText}: ${sms.contact_name}</strong>
                        <span style="font-size: 0.85em; color: #666;">${timeStr}</span>
                    </div>
                    <div style="color: #333; margin-left: 20px;">
                        ${sms.message}
                    </div>
                    ${sms.phone_number && sms.phone_number !== 'Ukjent' ? 
                        `<div style="font-size: 0.8em; color: #888; margin-top: 5px; margin-left: 20px;">${sms.phone_number}</div>` 
                        : ''}
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Feil ved lasting av SMS:', error);
        document.getElementById('sms-history-container').innerHTML = 
            '<div style="text-align: center; color: #d32f2f; padding: 20px;">⚠️ Kunne ikke laste SMS-historikk</div>';
    }
}

// === SMS Contacts Management ===
async function loadContacts() {
    console.log('Loading SMS contacts...');
    try {
        const response = await fetch('/sms_contacts');
        console.log('Contacts response status:', response.status);
        if (!response.ok) throw new Error('Kunne ikke laste kontakter');
        
        const contacts = await response.json();
        console.log('Loaded contacts:', contacts.length);
        const container = document.getElementById('contacts-list');
        
        if (contacts.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">Ingen kontakter ennå</div>';
            return;
        }
        
        let html = '';
        contacts.forEach(contact => {
            const statusIcon = contact.enabled ? '✅' : '❌';
            html += `
                <div style="padding: 12px; background: ${contact.enabled ? '#f1f8e9' : '#ffebee'}; border-left: 4px solid ${contact.enabled ? '#66bb6a' : '#ef5350'}; border-radius: 6px;">
                    <div>
                        <strong>${statusIcon} ${contact.name}</strong><br>
                        <span style="font-size: 0.9em; color: #666;">📱 ${contact.phone}</span><br>
                        <span style="font-size: 0.85em; color: #888;">Relasjon: ${contact.relation} | Prioritet: ${contact.priority}</span>
                    </div>
                    <div style="display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;">
                        <button onclick="editContact(${contact.id})" style="padding: 6px 12px; background: #2196f3; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; flex: 1; min-width: 80px;">
                            ✏️ Rediger
                        </button>
                        <button onclick="toggleContactEnabled(${contact.id}, ${!contact.enabled})" style="padding: 6px 12px; background: ${contact.enabled ? '#ff9800' : '#4caf50'}; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; flex: 1; min-width: 80px;">
                            ${contact.enabled ? '🔕 Deaktiver' : '🔔 Aktiver'}
                        </button>
                        <button onclick="deleteContact(${contact.id}, '${contact.name}')" style="padding: 6px 12px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; flex: 1; min-width: 80px;">
                            🗑️ Slett
                        </button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Feil ved lasting av kontakter:', error);
        document.getElementById('contacts-list').innerHTML = 
            '<div style="text-align: center; color: #d32f2f; padding: 20px;">⚠️ Kunne ikke laste kontakter</div>';
    }
}

function showAddContactForm() {
    document.getElementById('contact-form-title').textContent = 'Ny kontakt';
    document.getElementById('edit-contact-id').value = '';
    document.getElementById('add-contact-form').style.display = 'block';
    document.getElementById('new-contact-name').value = '';
    document.getElementById('new-contact-phone').value = '';
    document.getElementById('new-contact-relation').value = '';
    document.getElementById('new-contact-priority').value = '5';
}

function cancelAddContact() {
    document.getElementById('add-contact-form').style.display = 'none';
}

async function saveContact() {
    const editId = document.getElementById('edit-contact-id').value;
    const name = document.getElementById('new-contact-name').value.trim();
    const phone = document.getElementById('new-contact-phone').value.trim();
    const relation = document.getElementById('new-contact-relation').value.trim() || 'venn';
    const priority = parseInt(document.getElementById('new-contact-priority').value) || 5;
    
    if (!name || !phone) {
        alert('Navn og telefonnummer må fylles ut');
        return;
    }
    
    try {
        let response;
        if (editId) {
            // Update existing contact
            response = await fetch(`/sms_contacts/${editId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, phone, relation, enabled: true, priority })
            });
        } else {
            // Create new contact
            response = await fetch('/sms_contacts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, phone, relation, enabled: true, priority })
            });
        }
        
        const result = await response.json();
        if (result.success) {
            cancelAddContact();
            await loadContacts();
        } else {
            alert('Feil: ' + (result.error || 'Ukjent feil'));
        }
    } catch (error) {
        alert('Nettverksfeil: ' + error.message);
    }
}

async function deleteContact(id, name) {
    if (!confirm(`Er du sikker på at du vil slette kontakten "${name}"?`)) return;
    
    try {
        const response = await fetch(`/sms_contacts/${id}`, { method: 'DELETE' });
        const result = await response.json();
        
        if (result.success) {
            await loadContacts();
        } else {
            alert('Feil: ' + (result.error || result.message || 'Ukjent feil'));
        }
    } catch (error) {
        alert('Nettverksfeil: ' + error.message);
    }
}

async function editContact(id) {
    try {
        const response = await fetch('/sms_contacts');
        const contacts = await response.json();
        const contact = contacts.find(c => c.id === id);
        
        if (!contact) {
            alert('Kontakt ikke funnet');
            return;
        }
        
        // Populate form with contact data
        document.getElementById('contact-form-title').textContent = 'Rediger kontakt';
        document.getElementById('edit-contact-id').value = contact.id;
        document.getElementById('new-contact-name').value = contact.name;
        document.getElementById('new-contact-phone').value = contact.phone;
        document.getElementById('new-contact-relation').value = contact.relation;
        document.getElementById('new-contact-priority').value = contact.priority;
        document.getElementById('add-contact-form').style.display = 'block';
        
        // Scroll to form
        document.getElementById('add-contact-form').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (error) {
        alert('Feil ved lasting av kontakt: ' + error.message);
    }
}

async function toggleContactEnabled(id, newEnabledState) {
    try {
        // First fetch current contact data
        const getResponse = await fetch('/sms_contacts');
        const contacts = await getResponse.json();
        const contact = contacts.find(c => c.id === id);
        
        if (!contact) {
            alert('Kontakt ikke funnet');
            return;
        }
        
        // Update with new enabled state
        contact.enabled = newEnabledState;
        
        const response = await fetch(`/sms_contacts/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(contact)
        });
        
        const result = await response.json();
        if (result.success) {
            await loadContacts();
        } else {
            alert('Feil: ' + (result.error || result.message || 'Ukjent feil'));
        }
    } catch (error) {
        alert('Nettverksfeil: ' + error.message);
    }
}

// ============================================================================
// Backup Functions
// ============================================================================

async function loadBackupStatus() {
    try {
        const response = await fetch('/api/backup');
        const data = await response.json();
        
        const latestEl = document.getElementById('latest-backup');
        const listEl = document.getElementById('backup-list');
        
        if (data.status === 'success') {
            if (data.latest) {
                latestEl.textContent = data.latest;
                latestEl.style.color = '#667eea';
            } else {
                latestEl.textContent = 'Ingen backups funnet';
                latestEl.style.color = '#999';
            }
            
            if (data.backups && data.backups.length > 0) {
                listEl.innerHTML = data.backups.map(backup => 
                    `<div style="padding: 5px; border-bottom: 1px solid #ddd;">${backup}</div>`
                ).join('');
            } else {
                listEl.innerHTML = '<div style="color: #999;">Ingen backups</div>';
            }
        } else {
            latestEl.textContent = 'Feil: ' + (data.error || 'Ukjent feil');
            latestEl.style.color = '#e74c3c';
            listEl.innerHTML = '<div style="color: #e74c3c;">Kunne ikke laste backups</div>';
        }
    } catch (error) {
        console.error('Backup status error:', error);
        document.getElementById('latest-backup').textContent = 'Feil: ' + error.message;
        document.getElementById('backup-list').innerHTML = '<div style="color: #e74c3c;">Nettverksfeil</div>';
    }
}

async function createBackup() {
    const button = event.target;
    const originalText = button.textContent;
    
    // Confirm
    if (!confirm('Start backup til OneDrive? Dette kan ta 1-2 minutter.')) {
        return;
    }
    
    try {
        button.textContent = '⏳ Tar backup...';
        button.disabled = true;
        
        const response = await fetch('/api/backup/start', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✅ ' + data.message);
            await loadBackupStatus(); // Refresh backup list
        } else {
            alert('❌ ' + data.message + (data.error ? '\n\n' + data.error : ''));
        }
    } catch (error) {
        alert('❌ Nettverksfeil: ' + error.message);
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}

// System Stats
async function loadSystemStats() {
    try {
        const response = await fetch('/api/system/stats');
        const data = await response.json();
        
        // Update CPU temperature
        const cpuTempEl = document.getElementById('cpu-temp');
        if (data.cpu_temp !== null && data.cpu_temp !== undefined) {
            const temp = data.cpu_temp;
            let color = '#4caf50'; // Green
            if (temp > 70) color = '#ff9800'; // Orange
            if (temp > 80) color = '#f44336'; // Red
            cpuTempEl.innerHTML = `<span style="color: ${color};">${temp.toFixed(1)}°C</span>`;
        } else {
            cpuTempEl.textContent = 'N/A';
        }
        
        // Update memory
        const memoryEl = document.getElementById('memory-available');
        if (data.memory) {
            const mem = data.memory;
            const availableGB = (mem.available / 1024).toFixed(1);
            const totalGB = (mem.total / 1024).toFixed(1);
            let color = '#4caf50'; // Green
            if (mem.used_percent > 80) color = '#ff9800'; // Orange
            if (mem.used_percent > 90) color = '#f44336'; // Red
            memoryEl.innerHTML = `<span style="color: ${color};">${availableGB}GB / ${totalGB}GB</span>`;
        } else {
            memoryEl.textContent = 'N/A';
        }
    } catch (error) {
        console.error('Kunne ikke laste system stats:', error);
        document.getElementById('cpu-temp').textContent = 'N/A';
        document.getElementById('memory-available').textContent = 'N/A';
    }
}

// Load backup status on page load
document.addEventListener('DOMContentLoaded', () => {
    loadBackupStatus();
    // Refresh every 30 seconds
    setInterval(loadBackupStatus, 30000);
});
