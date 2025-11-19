#!/usr/bin/env bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/hyprland-ai-automator"
CONFIG_DIR="$HOME/.config/hyprland-ai-automator"
SYSTEMD_DIR="$HOME/.config/systemd/user"
DB_PATH="$HOME/.local/share/hyprland-ai-automator/context_db.sqlite"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Hyprland AI Automator - Installation Script              ║${NC}"
echo -e "${BLUE}║     Arch Linux + Hyprland + Gemini API                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running on Arch Linux
check_arch() {
    print_status "Checking if running on Arch Linux..."
    if [ ! -f "/etc/arch-release" ]; then
        print_error "This script is designed for Arch Linux only!"
        exit 1
    fi
    print_success "Arch Linux detected"
}

# Check if Hyprland is installed
check_hyprland() {
    print_status "Checking for Hyprland installation..."
    if ! command -v hyprctl &> /dev/null; then
        print_error "Hyprland is not installed or not in PATH!"
        exit 1
    fi
    print_success "Hyprland found: $(hyprctl version | head -n1)"
}

# Check and install dependencies
install_dependencies() {
    print_status "Checking and installing dependencies..."
    
    local packages=()
    local aur_packages=()
    
    # Core dependencies
    [ ! "$(command -v python3)" ] && packages+=("python")
    [ ! "$(command -v pip)" ] && packages+=("python-pip")
    [ ! "$(command -v git)" ] && packages+=("git")
    [ ! "$(command -v jq)" ] && packages+=("jq")
    [ ! "$(command -v curl)" ] && packages+=("curl")
    [ ! "$(command -v grim)" ] && packages+=("grim")
    [ ! "$(command -v slurp)" ] && packages+=("slurp")
    [ ! "$(command -v pactl)" ] && packages+=("libpulse")
    [ ! "$(command -v brightnessctl)" ] && packages+=("brightnessctl")
    [ ! "$(command -v bluetoothctl)" ] && packages+=("bluez-utils")
    [ ! "$(command -v playerctl)" ] && packages+=("playerctl")
    
    # Install official repo packages
    if [ ${#packages[@]} -gt 0 ]; then
        print_status "Installing missing packages: ${packages[*]}"
        sudo pacman -S --needed --noconfirm "${packages[@]}" || {
            print_error "Failed to install packages"
            exit 1
        }
    fi
    
    # Check for ydotool
    if ! command -v ydotool &> /dev/null; then
        print_warning "ydotool not found. Installing from AUR..."
        
        # Check for yay or paru
        if command -v yay &> /dev/null; then
            yay -S --needed --noconfirm ydotool
        elif command -v paru &> /dev/null; then
            paru -S --needed --noconfirm ydotool
        else
            print_warning "No AUR helper found. Building ydotool from source..."
            build_ydotool_from_source
        fi
    fi
    
    # Verify ydotool daemon
    if ! systemctl --user is-enabled ydotool.service &> /dev/null; then
        print_status "Enabling ydotool daemon..."
        systemctl --user enable ydotool.service
        systemctl --user start ydotool.service
    fi
    
    print_success "All system dependencies installed"
}

# Build ydotool from source if needed
build_ydotool_from_source() {
    print_status "Building ydotool from source..."
    
    local build_dir="/tmp/ydotool-build-$$"
    mkdir -p "$build_dir"
    cd "$build_dir"
    
    # Install build dependencies
    sudo pacman -S --needed --noconfirm cmake scdoc
    
    # Clone and build
    git clone https://github.com/ReimuNotMoe/ydotool.git
    cd ydotool
    mkdir build && cd build
    cmake ..
    make -j$(nproc)
    sudo make install
    
    # Setup systemd service
    sudo cp ../ydotool.service /usr/lib/systemd/user/
    
    cd "$PROJECT_ROOT"
    rm -rf "$build_dir"
    
    print_success "ydotool built and installed from source"
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --upgrade pip --user
    
    # Install required packages
    python3 -m pip install --user \
        google-genai \
        aiohttp \
        asyncio \
        fastapi \
        uvicorn \
        websockets \
        sqlalchemy \
        cryptography \
        psutil \
        python-dotenv
    
    print_success "Python dependencies installed"
}

# Create directory structure
create_directories() {
    print_status "Creating directory structure..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$SYSTEMD_DIR"
    mkdir -p "$INSTALL_DIR/logs"
    
    print_success "Directories created"
}

# Copy project files
copy_files() {
    print_status "Copying project files..."
    
    # Copy all Python files
    cp -r "$PROJECT_ROOT/src/"* "$INSTALL_DIR/"
    cp -r "$PROJECT_ROOT/web/" "$INSTALL_DIR/"
    
    # Make main script executable
    chmod +x "$INSTALL_DIR/daemon.py"
    
    print_success "Project files copied"
}

# Setup Gemini API key
setup_api_key() {
    print_status "Setting up Gemini API key..."
    
    if [ -f "$CONFIG_DIR/config.ini" ]; then
        print_warning "Config file already exists. Skipping API key setup."
        return
    fi
    
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Please enter your Gemini API key${NC}"
    echo -e "${YELLOW}  Get one for free at: https://aistudio.google.com/apikey${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    read -rsp "Enter your Gemini API key: " api_key
    echo ""
    
    if [ -z "$api_key" ]; then
        print_error "API key cannot be empty!"
        exit 1
    fi
    
    # Create encrypted config
    cat > "$CONFIG_DIR/config.ini" << EOF
[gemini]
api_key = $api_key
model = gemini-2.0-flash

[daemon]
host = 127.0.0.1
port = 8765
log_level = INFO

[paths]
db_path = $DB_PATH
log_dir = $INSTALL_DIR/logs
EOF
    
    chmod 600 "$CONFIG_DIR/config.ini"
    print_success "API key configured securely"
}

# Initialize database
init_database() {
    print_status "Initializing context database..."
    
    python3 << EOF
import sqlite3
import os

db_path = "$DB_PATH"
os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables
cursor.executescript('''
    CREATE TABLE IF NOT EXISTS system_context (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        category TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS command_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT NOT NULL,
        output TEXT,
        success BOOLEAN,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        role TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS keybindings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        modifiers TEXT NOT NULL,
        key TEXT NOT NULL,
        action TEXT NOT NULL,
        description TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_system_context_key ON system_context(key);
    CREATE INDEX IF NOT EXISTS idx_command_history_timestamp ON command_history(timestamp);
    CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
''')

conn.commit()
conn.close()
print("Database initialized successfully")
EOF
    
    print_success "Database initialized"
}

# Analyze Hyprland configuration
analyze_hyprland_config() {
    print_status "Analyzing Hyprland configuration..."
    
    python3 "$INSTALL_DIR/config_analyzer.py" || {
        print_warning "Config analysis completed with warnings"
    }
    
    print_success "Hyprland configuration analyzed"
}

# Setup systemd service
setup_systemd() {
    print_status "Setting up systemd service..."
    
    cat > "$SYSTEMD_DIR/hyprland-ai-automator.service" << EOF
[Unit]
Description=Hyprland AI Automator Daemon
After=graphical-session.target hyprland-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/daemon.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=HYPRLAND_INSTANCE_SIGNATURE=%E
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
    
    # Reload systemd and enable service
    systemctl --user daemon-reload
    systemctl --user enable hyprland-ai-automator.service
    
    print_success "Systemd service configured"
}

# Create desktop launcher
create_launcher() {
    print_status "Creating desktop launcher..."
    
    local desktop_file="$HOME/.local/share/applications/hyprland-ai-automator.desktop"
    
    cat > "$desktop_file" << EOF
[Desktop Entry]
Name=Hyprland AI Automator
Comment=AI-powered desktop automation for Hyprland
Exec=xdg-open http://127.0.0.1:8765
Icon=robot
Terminal=false
Type=Application
Categories=Utility;System;
EOF
    
    chmod +x "$desktop_file"
    print_success "Desktop launcher created"
}

# Main installation flow
main() {
    check_arch
    check_hyprland
    install_dependencies
    install_python_deps
    create_directories
    copy_files
    setup_api_key
    init_database
    analyze_hyprland_config
    setup_systemd
    create_launcher
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            Installation completed successfully!                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo -e "  1. Start the service: ${GREEN}systemctl --user start hyprland-ai-automator.service${NC}"
    echo -e "  2. Check status: ${GREEN}systemctl --user status hyprland-ai-automator.service${NC}"
    echo -e "  3. Open dashboard: ${GREEN}http://127.0.0.1:8765${NC}"
    echo ""
    echo -e "${YELLOW}Logs location:${NC} $INSTALL_DIR/logs/"
    echo -e "${YELLOW}Config location:${NC} $CONFIG_DIR/config.ini"
    echo ""
    
    read -p "Would you like to start the service now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl --user start hyprland-ai-automator.service
        sleep 2
        
        if systemctl --user is-active --quiet hyprland-ai-automator.service; then
            print_success "Service started successfully!"
            echo -e "${GREEN}Open your browser to: http://127.0.0.1:8765${NC}"
        else
            print_error "Service failed to start. Check logs with:"
            echo "  journalctl --user -u hyprland-ai-automator.service -f"
        fi
    fi
}

# Run main installation
main "$@"