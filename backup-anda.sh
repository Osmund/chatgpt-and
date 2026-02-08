#!/bin/bash
# =============================================================================
# Anda Backup Script
# Backs up critical files to OneDrive using rclone
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: .env file not found at $ENV_FILE${NC}"
    exit 1
fi

# Load DUCK_NAME from .env
DUCK_NAME=$(grep -E '^DUCK_NAME=' "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | tr -d '\n' | tr -d '\r')

if [ -z "$DUCK_NAME" ]; then
    echo -e "${YELLOW}Warning: DUCK_NAME not set in .env, using 'samantha' as default${NC}"
    DUCK_NAME="samantha"
fi

# Configuration
RCLONE_REMOTE="anda-backup"  # Name from rclone config
BACKUP_DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_BASE="duck-backups/${DUCK_NAME}"
BACKUP_PATH="${BACKUP_BASE}/${BACKUP_DATE}"
TEMP_DIR="/tmp/anda-backup-${BACKUP_DATE}"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  Anda Backup - ${DUCK_NAME}${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo -e "📅 Backup date: ${GREEN}${BACKUP_DATE}${NC}"
echo -e "🦆 Duck name: ${GREEN}${DUCK_NAME}${NC}"
echo -e "📦 Destination: ${GREEN}${RCLONE_REMOTE}:${BACKUP_PATH}${NC}"
echo ""

# Check if rclone is configured
if ! rclone listremotes | grep -q "^${RCLONE_REMOTE}:$"; then
    echo -e "${RED}Error: rclone remote '${RCLONE_REMOTE}' not configured!${NC}"
    echo -e "${YELLOW}Please run: rclone config${NC}"
    echo -e "${YELLOW}And create a remote named '${RCLONE_REMOTE}' for your OneDrive${NC}"
    exit 1
fi

# Create temporary backup directory
echo -e "${BLUE}[1/6]${NC} Creating temporary backup directory..."
mkdir -p "$TEMP_DIR"

# Backup database
echo -e "${BLUE}[2/6]${NC} Backing up database..."
if [ -f "$SCRIPT_DIR/duck_memory.db" ]; then
    cp "$SCRIPT_DIR/duck_memory.db" "$TEMP_DIR/"
    echo -e "  ${GREEN}✓${NC} duck_memory.db"
else
    echo -e "  ${YELLOW}⚠${NC} duck_memory.db not found"
fi

# Backup .env file
echo -e "${BLUE}[3/6]${NC} Backing up configuration..."
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$TEMP_DIR/"
    echo -e "  ${GREEN}✓${NC} .env"
else
    echo -e "  ${RED}✗${NC} .env not found"
fi

# Backup identity and config files
mkdir -p "$TEMP_DIR/config"
for cfg in "$SCRIPT_DIR"/config/*_identity.json "$SCRIPT_DIR"/config/locations.json "$SCRIPT_DIR"/config/personalities.json "$SCRIPT_DIR"/config/messages.json; do
    if [ -f "$cfg" ]; then
        cp "$cfg" "$TEMP_DIR/config/"
        echo -e "  ${GREEN}✓${NC} config/$(basename "$cfg")"
    fi
done

# Backup wake word models
mkdir -p "$TEMP_DIR/wake_word_models"
for model in "$SCRIPT_DIR"/porcupine/*.ppn "$SCRIPT_DIR"/openwakeword_models/*.onnx; do
    if [ -f "$model" ]; then
        cp "$model" "$TEMP_DIR/wake_word_models/"
        echo -e "  ${GREEN}✓${NC} $(basename "$model")"
    fi
done

# Backup wake word sensitivity
if [ -f "$SCRIPT_DIR/wake_word_sensitivity.txt" ]; then
    cp "$SCRIPT_DIR/wake_word_sensitivity.txt" "$TEMP_DIR/"
    echo -e "  ${GREEN}✓${NC} wake_word_sensitivity.txt"
fi

# Backup sleep mode state
if [ -f "$SCRIPT_DIR/sleep_mode.json" ]; then
    cp "$SCRIPT_DIR/sleep_mode.json" "$TEMP_DIR/"
    echo -e "  ${GREEN}✓${NC} sleep_mode.json"
fi

# Backup voice/face profiles from Duck-Vision Pi 5 (remote)
VISION_HOST="${DUCK_VISION_HOST:-192.168.10.197}"
VISION_USER="${DUCK_VISION_USER:-admog}"
VISION_DATA="/home/admog/Code/Duck-Vision/data"

if ssh -o ConnectTimeout=5 -o BatchMode=yes "${VISION_USER}@${VISION_HOST}" "test -d ${VISION_DATA}" 2>/dev/null; then
    mkdir -p "$TEMP_DIR/duck-vision"
    echo -e "  📡 Duck-Vision Pi 5 tilgjengelig, henter profiler..."
    if scp -r -o ConnectTimeout=5 "${VISION_USER}@${VISION_HOST}:${VISION_DATA}/known_voices" "$TEMP_DIR/duck-vision/" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} duck-vision/known_voices (fra Pi 5)"
    fi
    if scp -r -o ConnectTimeout=5 "${VISION_USER}@${VISION_HOST}:${VISION_DATA}/known_faces" "$TEMP_DIR/duck-vision/" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} duck-vision/known_faces (fra Pi 5)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Duck-Vision Pi 5 ikke tilgjengelig - hopper over stemme/ansiktsprofiler"
fi

# Backup systemd services
echo -e "${BLUE}[4/6]${NC} Backing up systemd services..."
mkdir -p "$TEMP_DIR/systemd"
for service in chatgpt-duck.service duck-control.service fan-control.service auto-hotspot.service anda-backup.service anda-backup.timer; do
    if [ -f "/etc/systemd/system/$service" ]; then
        sudo cp "/etc/systemd/system/$service" "$TEMP_DIR/systemd/"
        echo -e "  ${GREEN}✓${NC} $service"
    fi
done

# Create backup metadata
echo -e "${BLUE}[5/6]${NC} Creating backup metadata..."
cat > "$TEMP_DIR/backup-info.txt" <<EOF
Anda Backup Information
=======================

Duck Name: ${DUCK_NAME}
Backup Date: ${BACKUP_DATE}
Hostname: $(hostname)
Pi Model: $(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)
Kernel: $(uname -r)

Files backed up:
- duck_memory.db (database with personality and memories)
- .env (API keys and configuration)
- config/*_identity.json (duck identity)
- config/locations.json, personalities.json, messages.json
- porcupine/*.ppn / openwakeword_models/*.onnx (wake word models)
- wake_word_sensitivity.txt, sleep_mode.json (runtime state)
- duck-vision/known_voices, known_faces (recognition profiles)
- systemd services

Generated by: backup-anda.sh
EOF
echo -e "  ${GREEN}✓${NC} backup-info.txt"

# Upload to OneDrive using rclone
echo ""
echo -e "${BLUE}Uploading to OneDrive...${NC}"
if rclone copy "$TEMP_DIR" "${RCLONE_REMOTE}:${BACKUP_PATH}" --progress; then
    echo ""
    echo -e "${GREEN}✓ Backup completed successfully!${NC}"
    echo -e "📍 Location: ${RCLONE_REMOTE}:${BACKUP_PATH}"
else
    echo -e "${RED}✗ Backup failed!${NC}"
    echo -e "Temporary files kept at: $TEMP_DIR"
    exit 1
fi

# Clean up temporary directory
echo ""
echo -e "${BLUE}Cleaning up...${NC}"
rm -rf "$TEMP_DIR"
echo -e "${GREEN}✓ Temporary files removed${NC}"

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}  Backup Complete! 🦆${NC}"
echo -e "${GREEN}==============================================================================${NC}"
