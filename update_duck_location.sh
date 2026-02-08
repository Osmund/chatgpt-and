#!/bin/bash
# Oppdater Andas nåværende lokasjon
# Bruk: ./update_duck_location.sh Stavanger
# eller: ./update_duck_location.sh Sokndal

if [ -z "$1" ]; then
    echo "Bruk: $0 <lokasjon>"
    echo "Eksempel: $0 Stavanger"
    echo "Eksempel: $0 Sokndal"
    
    # Vis nåværende lokasjon
    echo ""
    echo "Nåværende lokasjon:"
    sqlite3 /home/admog/Code/chatgpt-and/duck_memory.db \
        "SELECT value FROM profile_facts WHERE key = 'duck_current_location';"
    exit 1
fi

LOCATION="$1"

echo "Oppdaterer Andas lokasjon til: $LOCATION"

sqlite3 /home/admog/Code/chatgpt-and/duck_memory.db << EOF
INSERT OR REPLACE INTO profile_facts (key, value, topic, confidence, source, last_updated) 
VALUES ('duck_current_location', '$LOCATION', 'location', 1.0, 'user', datetime('now'));

SELECT '✅ Andas lokasjon oppdatert til: ' || value 
FROM profile_facts 
WHERE key = 'duck_current_location';
EOF

echo ""
echo "Anda vet nå at hun er i $LOCATION"
echo "Når du spør om været, vil hun bruke denne lokasjonen."
