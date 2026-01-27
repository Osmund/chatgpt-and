#!/bin/bash
# =============================================================================
# Anda Bootstrap Script
# Automated setup for fresh Raspberry Pi OS installation
# =============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
cat << "EOF"
    ___           __     
   /   |  ____   ____/ /____ _
  / /| | / __ \ / __  // __ `/
 / ___ |/ / / // /_/ // /_/ / 
/_/  |_/_/ /_/ \__,_/ \__,_/  
                              
Bootstrap Script v1.0
EOF
echo -e "${NC}"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  Anda Bootstrap - Automated Installation${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Error: Do not run this script as root!${NC}"
    echo -e "${YELLOW}Run as normal user: bash bootstrap-anda.sh${NC}"
    exit 1
fi

# Prompt for duck name
echo -e "${CYAN}What is the name of this duck?${NC}"
read -p "Duck name (default: samantha): " DUCK_NAME
DUCK_NAME=${DUCK_NAME:-samantha}
echo -e "Setting up: ${GREEN}${DUCK_NAME}${NC}"
echo ""

# Step 1: System update
echo -e "${BLUE}[1/10]${NC} Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Step 2: Install system dependencies
echo -e "${BLUE}[2/10]${NC} Installing system dependencies..."
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    git curl wget \
    rclone \
    portaudio19-dev python3-pyaudio \
    espeak ffmpeg \
    sox libsox-fmt-all \
    sqlite3 \
    alsa-utils \
    pigpio python3-pigpio

# Step 3: Clone repository
echo -e "${BLUE}[3/10]${NC} Cloning Anda repository from GitHub..."
INSTALL_DIR="$HOME/Code/chatgpt-and"
mkdir -p "$HOME/Code"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory already exists, pulling latest changes...${NC}"
    cd "$INSTALL_DIR"
    git pull
else
    cd "$HOME/Code"
    git clone https://github.com/YOUR_USERNAME/chatgpt-and.git
    cd chatgpt-and
fi

# Step 4: Configure rclone (if not already configured)
echo -e "${BLUE}[4/10]${NC} Checking rclone configuration..."
if ! rclone listremotes | grep -q "^anda-backup:$"; then
    echo -e "${YELLOW}rclone not configured for OneDrive.${NC}"
    echo -e "${CYAN}Please follow the prompts to set up OneDrive access:${NC}"
    echo ""
    echo "1. Choose 'n' for New remote"
    echo "2. Name it: ${GREEN}anda-backup${NC}"
    echo "3. Choose 'onedrive' from the list"
    echo "4. Follow the OAuth flow in your browser"
    echo ""
    read -p "Press Enter to start rclone config..."
    rclone config
else
    echo -e "${GREEN}✓ rclone already configured${NC}"
fi

# Step 5: Restore from backup
echo -e "${BLUE}[5/10]${NC} Checking for existing backups..."
LATEST_BACKUP=$(rclone lsf "anda-backup:duck-backups/${DUCK_NAME}/" --dirs-only 2>/dev/null | sort -r | head -n1 | tr -d '/')

if [ -n "$LATEST_BACKUP" ]; then
    echo -e "${GREEN}Found backup: ${LATEST_BACKUP}${NC}"
    read -p "Restore from this backup? (y/n): " RESTORE_CHOICE
    
    if [ "$RESTORE_CHOICE" = "y" ]; then
        echo -e "${BLUE}Downloading backup...${NC}"
        BACKUP_PATH="duck-backups/${DUCK_NAME}/${LATEST_BACKUP}"
        
        # Download .env
        if rclone copy "anda-backup:${BACKUP_PATH}/.env" "$INSTALL_DIR/" --progress; then
            echo -e "${GREEN}✓ .env restored${NC}"
            chmod 600 "$INSTALL_DIR/.env"
        fi
        
        # Download database
        if rclone copy "anda-backup:${BACKUP_PATH}/duck_memory.db" "$INSTALL_DIR/" --progress; then
            echo -e "${GREEN}✓ duck_memory.db restored${NC}"
        fi
        
        # Download music
        if rclone copy "anda-backup:${BACKUP_PATH}/musikk/" "$INSTALL_DIR/musikk/" --progress; then
            echo -e "${GREEN}✓ musik restored${NC}"
        fi
        
        # Download systemd services
        mkdir -p /tmp/anda-systemd
        if rclone copy "anda-backup:${BACKUP_PATH}/systemd/" /tmp/anda-systemd/ --progress; then
            echo -e "${GREEN}✓ systemd services downloaded${NC}"
        fi
    fi
else
    echo -e "${YELLOW}No backup found for ${DUCK_NAME}${NC}"
    echo -e "${YELLOW}You will need to create .env manually after installation${NC}"
fi

# If no .env exists, create from example
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo -e "${YELLOW}Creating .env from template...${NC}"
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    
    # Set DUCK_NAME
    sed -i "s/^DUCK_NAME=.*/DUCK_NAME=${DUCK_NAME}/" "$INSTALL_DIR/.env"
    
    echo -e "${RED}⚠ Important: Edit $INSTALL_DIR/.env and add your API keys!${NC}"
fi

# Step 6: Install Python dependencies
echo -e "${BLUE}[6/10]${NC} Installing Python packages..."
cd "$INSTALL_DIR"
pip3 install -r requirements.txt --break-system-packages

# Step 7: Verify Porcupine wake word files
echo -e "${BLUE}[7/10]${NC} Checking Porcupine wake word files..."
if [ -f "$INSTALL_DIR/Quack-quack.ppn" ] && [ -d "$INSTALL_DIR/porcupine" ]; then
    echo -e "${GREEN}✓ Porcupine wake word files found${NC}"
else
    echo -e "${YELLOW}⚠ Wake word files missing - må lastes opp manuelt${NC}"
    echo -e "${YELLOW}  Se GitHub repository for *.ppn filer${NC}"
fi

# Step 8: Configure MAX98357A audio
echo -e "${BLUE}[8/10]${NC} Configuring MAX98357A audio amplifier..."
bash "$INSTALL_DIR/setup_max98357a.sh"

# Step 9: Install systemd services
echo -e "${BLUE}[9/10]${NC} Installing systemd services..."

# Copy services to systemd directory
if [ -d "/tmp/anda-systemd" ]; then
    sudo cp /tmp/anda-systemd/*.service /etc/systemd/system/
else
    sudo cp "$INSTALL_DIR/"*.service /etc/systemd/system/
fi

# Enable and start pigpiod
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable chatgpt-duck.service
sudo systemctl enable duck-control.service
sudo systemctl enable fan-control.service
sudo systemctl enable auto-hotspot.service
sudo systemctl enable anda-backup.timer

echo -e "${GREEN}✓ Services installed and enabled${NC}"

# Step 10: Final setup
echo -e "${BLUE}[10/10]${NC} Final configuration..."

# Make scripts executable
chmod +x "$INSTALL_DIR/"*.sh

# Create database if it doesn't exist
if [ ! -f "$INSTALL_DIR/duck_memory.db" ]; then
    echo -e "${YELLOW}Creating new database...${NC}"
    sqlite3 "$INSTALL_DIR/duck_memory.db" < "$INSTALL_DIR/schema.sql" 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}  ✓ Bootstrap Complete! 🦆${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo ""
echo -e "1. ${YELLOW}Edit API keys:${NC} nano $INSTALL_DIR/.env"
echo -e "2. ${YELLOW}Test audio:${NC} speaker-test -t wav -c 2 -l 1"
echo -e "3. ${YELLOW}Start Anda:${NC} sudo systemctl start chatgpt-duck.service"
echo -e "4. ${YELLOW}Check logs:${NC} journalctl -u chatgpt-duck.service -f"
echo ""
echo -e "${CYAN}Services will start automatically on next reboot.${NC}"
echo ""
echo -e "${YELLOW}Reboot now? (y/n):${NC} "
read -p "" REBOOT_CHOICE

if [ "$REBOOT_CHOICE" = "y" ]; then
    echo -e "${GREEN}Rebooting...${NC}"
    sudo reboot
else
    echo -e "${CYAN}Remember to reboot when ready!${NC}"
fi
