#!/bin/bash
# Database backup script for ChatGPT Duck
# Tar backup av både database og session filer

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="duck_backup_${TIMESTAMP}"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

echo "🦆 ChatGPT Duck - Database Backup"
echo "=================================="
echo ""

# Opprett backup-mappe hvis den ikke eksisterer
mkdir -p "$BACKUP_DIR"

# Opprett backup-mappe for denne backupen
mkdir -p "$BACKUP_PATH"

echo "📦 Tar backup..."
echo "Backup-sti: $BACKUP_PATH"
echo ""

# Backup database fil
if [ -f "$PROJECT_DIR/duck_memory.db" ]; then
    cp "$PROJECT_DIR/duck_memory.db" "$BACKUP_PATH/"
    echo "✅ duck_memory.db"
else
    echo "⚠️  duck_memory.db ikke funnet"
fi

# Backup chatgpt_voice database
if [ -f "$PROJECT_DIR/chatgpt_voice.db" ]; then
    cp "$PROJECT_DIR/chatgpt_voice.db" "$BACKUP_PATH/"
    echo "✅ chatgpt_voice.db"
fi

# Backup session filer (hvis de finnes)
if [ -f "/tmp/duck_current_user.json" ]; then
    cp "/tmp/duck_current_user.json" "$BACKUP_PATH/"
    echo "✅ duck_current_user.json"
fi

# Backup embedding filer
for file in "$PROJECT_DIR"/*-embedding.bin; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_PATH/"
        echo "✅ $(basename "$file")"
    fi
done

# Lag metadata fil
cat > "$BACKUP_PATH/backup_info.txt" << EOF
ChatGPT Duck - Database Backup
==============================

Backup tid: $(date '+%Y-%m-%d %H:%M:%S')
Hostname: $(hostname)
Bruker: $(whoami)

Filer inkludert:
$(ls -lh "$BACKUP_PATH" | tail -n +2)

Database statistikk (før backup):
EOF

# Legg til database stats hvis sqlite3 er tilgjengelig
if command -v sqlite3 &> /dev/null; then
    if [ -f "$PROJECT_DIR/duck_memory.db" ]; then
        echo "" >> "$BACKUP_PATH/backup_info.txt"
        echo "duck_memory.db:" >> "$BACKUP_PATH/backup_info.txt"
        sqlite3 "$PROJECT_DIR/duck_memory.db" "
            SELECT 'Meldinger: ' || COUNT(*) FROM messages;
            SELECT 'Minner: ' || COUNT(*) FROM memories;
            SELECT 'Facts: ' || COUNT(*) FROM profile_facts;
        " >> "$BACKUP_PATH/backup_info.txt" 2>/dev/null || true
    fi
fi

# Komprimer backup
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

BACKUP_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)

echo ""
echo "✅ Backup fullført!"
echo ""
echo "📁 Backup fil: ${BACKUP_NAME}.tar.gz"
echo "💾 Størrelse: $BACKUP_SIZE"
echo "📍 Plassering: $BACKUP_DIR"
echo ""

# Vis de 5 siste backupene
echo "📋 Siste backups:"
ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -5 | awk '{print "   " $9 " (" $5 ")"}'
echo ""

# Slett backups eldre enn 30 dager (optional, kommenter ut hvis du vil beholde alt)
# find "$BACKUP_DIR" -name "duck_backup_*.tar.gz" -mtime +30 -delete

echo "💡 For å restore: ./scripts/restore_database.sh ${BACKUP_NAME}.tar.gz"
