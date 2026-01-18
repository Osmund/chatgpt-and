#!/bin/bash
# Nattlig personlighetsanalyse - Kjøres kl 03:00 hver natt
# Analyserer siste 7 dagers samtaler og oppdaterer Andas personlighetsprofil

cd /home/admog/Code/chatgpt-and

# Last environment variables
export $(cat .env | grep -v '^#' | xargs)

# Kjør analyse med o1 reasoning model
/usr/bin/python3 src/personality_analyzer.py --model gpt4o --days 7 >> /var/log/anda-personality-analysis.log 2>&1

# Restart Anda service for å laste ny profil
/usr/bin/sudo /bin/systemctl restart chatgpt-duck.service

echo "$(date): Personality analysis completed" >> /var/log/anda-personality-analysis.log
