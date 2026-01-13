#!/bin/bash
# Database restore script for ChatGPT Duck
# Restore fra backup tar.gz fil

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"

echo "🦆 ChatGPT Duck - Database Restore"
echo "=================================="
echo ""

# Sjekk om backup-fil er spesifisert
if [ -z "$1" ]; then
    echo "❌ Feil: Ingen backup-fil spesifisert"
    echo ""
    echo "Bruk: ./scripts/restore_database.sh <backup_fil.tar.gz>"
    echo ""
    echo "Tilgjengelige backups:"
    ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -10 | awk '{print "   " $9 " (" $5 ", " $6 " " $7 ")"}'
    exit 1
fi

BACKUP_FILE="$1"

# Sjekk om filen eksisterer
if [ ! -f "$BACKUP_FILE" ]; then
    # Prøv i backup_dir
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    else
        echo "❌ Feil: Backup-fil ikke funnet: $BACKUP_FILE"
        exit 1
    fi
fi

echo "📦 Restore fra: $(basename "$BACKUP_FILE")"
echo ""

# Bekreftelse
read -p "⚠️  Dette vil overskrive eksisterende database. Er du sikker? (ja/nei): " -r
echo ""
if [[ ! $REPLY =~ ^[Jj][Aa]$ ]]; then
    echo "❌ Restore avbrutt"
    exit 0
fi

# Stopp tjenester først
echo "🛑 Stopper ChatGPT Duck tjenester..."
sudo systemctl stop chatgpt-duck 2>/dev/null || true
sudo systemctl stop duck-control 2>/dev/null || true
echo ""

# Ta backup av nåværende tilstand før restore (safety net)
SAFETY_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
echo "💾 Tar sikkerhetskopi av nåværende tilstand..."
if [ -f "$PROJECT_DIR/duck_memory.db" ]; then
    tar -czf "$SAFETY_BACKUP" -C "$PROJECT_DIR" \
        duck_memory.db \
        chatgpt_voice.db \
        *-embedding.bin 2>/dev/null || true
    echo "✅ Sikkerhetskopi lagret: $(basename "$SAFETY_BACKUP")"
fi
echo ""

# Pakk ut backup
TEMP_DIR=$(mktemp -d)
echo "📂 Pakker ut backup..."
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Finn backup-mappen (første subdir i temp)
BACKUP_CONTENT=$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)

if [ -z "$BACKUP_CONTENT" ]; then
    echo "❌ Feil: Kunne ikke finne backup-innhold"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "✅ Backup pakket ut"
echo ""

# Vis backup info
if [ -f "$BACKUP_CONTENT/backup_info.txt" ]; then
    echo "📋 Backup informasjon:"
    echo "---"
    cat "$BACKUP_CONTENT/backup_info.txt"
    echo "---"
    echo ""
fi

# Restore filer
echo "♻️  Restorer filer..."

if [ -f "$BACKUP_CONTENT/duck_memory.db" ]; then
    cp "$BACKUP_CONTENT/duck_memory.db" "$PROJECT_DIR/"
    echo "✅ duck_memory.db"
fi

if [ -f "$BACKUP_CONTENT/chatgpt_voice.db" ]; then
    cp "$BACKUP_CONTENT/chatgpt_voice.db" "$PROJECT_DIR/"
    echo "✅ chatgpt_voice.db"
fi

# Restore embedding filer
for file in "$BACKUP_CONTENT"/*-embedding.bin; do
    if [ -f "$file" ]; then
        cp "$file" "$PROJECT_DIR/"
        echo "✅ $(basename "$file")"
    fi
done

# Rydd opp
rm -rf "$TEMP_DIR"

# Sett riktige permissions
chown admog:admog "$PROJECT_DIR"/*.db 2>/dev/null || true
chmod 644 "$PROJECT_DIR"/*.db 2>/dev/null || true

echo ""
echo "✅ Restore fullført!"
echo ""

# Start tjenester igjen
read -p "🚀 Start ChatGPT Duck tjenester nå? (ja/nei): " -r
echo ""
if [[ $REPLY =~ ^[Jj][Aa]$ ]]; then
    echo "🚀 Starter tjenester..."
    sudo systemctl start chatgpt-duck
    sudo systemctl start duck-control
    echo ""
    echo "✅ Tjenester startet"
    sleep 2
    sudo systemctl status chatgpt-duck --no-pager -l | head -15
else
    echo "💡 Start tjenester manuelt med:"
    echo "   sudo systemctl start chatgpt-duck"
    echo "   sudo systemctl start duck-control"
fi

echo ""
echo "💾 Sikkerhetskopi av gammel database: $(basename "$SAFETY_BACKUP")"
