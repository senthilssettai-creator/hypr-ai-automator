# Project Structure

This document shows the complete file organization for the Hyprland AI Automator project.

## Directory Layout

```
hyprland-ai-automator/
│
├── install.sh                          # Main installation script
├── requirements.txt                    # Python dependencies
├── README.md                          # Project documentation
├── LICENSE                            # MIT License
├── .gitignore                        # Git ignore rules
│
├── src/                              # Source code directory
│   ├── daemon.py                     # Main daemon entry point
│   │
│   ├── core/                         # Core functionality modules
│   │   ├── __init__.py
│   │   ├── hyprland_connector.py     # Hyprland integration & events
│   │   ├── action_dispatcher.py      # Command execution engine
│   │   ├── system_monitor.py         # System resource monitoring
│   │   └── context_manager.py        # Database & context storage
│   │
│   ├── ai/                           # AI integration
│   │   ├── __init__.py
│   │   └── gemini_client.py          # Gemini API client
│   │
│   ├── utils/                        # Utility modules
│   │   ├── __init__.py
│   │   ├── config.py                 # Configuration manager
│   │   └── logger.py                 # Logging setup
│   │
│   ├── config_analyzer.py            # Hyprland config parser
│   │
│   └── web/                          # Web interface
│       ├── __init__.py
│       ├── server.py                 # FastAPI web server
│       └── static/                   # Static web files
│           ├── index.html            # Main dashboard
│           ├── styles.css            # (Optional) Separate CSS
│           └── app.js                # (Optional) Separate JS
│
├── scripts/                          # Additional helper scripts
│   ├── test_connection.py           # Test Hyprland connection
│   ├── backup_db.sh                 # Backup database
│   └── reset_config.sh              # Reset configuration
│
├── tests/                           # Unit tests (optional)
│   ├── __init__.py
│   ├── test_hyprland.py
│   ├── test_dispatcher.py
│   └── test_gemini.py
│
├── docs/                            # Additional documentation
│   ├── INSTALLATION.md
│   ├── USAGE.md
│   ├── API.md
│   └── TROUBLESHOOTING.md
│
└── .github/                         # GitHub specific files
    ├── workflows/
    │   └── ci.yml                   # CI/CD workflow
    └── ISSUE_TEMPLATE/
        └── bug_report.md
```

## File Purposes

### Root Files
- **install.sh**: Complete installation automation script
- **requirements.txt**: Python package dependencies
- **README.md**: Main project documentation and quick start
- **LICENSE**: MIT License
- **.gitignore**: Ignore logs, cache, and sensitive files

### Source Code (src/)

#### Main Daemon
- **daemon.py**: Orchestrates all subsystems, main entry point

#### Core Modules (src/core/)
- **hyprland_connector.py**: 
  - Connects to Hyprland sockets
  - Listens for events
  - Executes dispatchers
  - Queries system state

- **action_dispatcher.py**:
  - Executes actions from AI responses
  - Handles keyboard/mouse input via ydotool
  - Manages shell commands
  - Controls system functions

- **system_monitor.py**:
  - Monitors CPU, memory, disk usage
  - Tracks network, audio, battery
  - Provides real-time system state

- **context_manager.py**:
  - Manages SQLite database
  - Stores conversations, commands, keybindings
  - Provides system context to AI

#### AI Integration (src/ai/)
- **gemini_client.py**:
  - Interfaces with Google Gemini API
  - Builds context-rich prompts
  - Parses JSON responses
  - Handles errors gracefully

#### Utilities (src/utils/)
- **config.py**: Configuration file management
- **logger.py**: Logging setup and handlers

#### Configuration Analysis
- **config_analyzer.py**: Parses Hyprland config files and extracts keybindings

#### Web Interface (src/web/)
- **server.py**: FastAPI web server with WebSocket support
- **static/index.html**: Interactive dashboard UI

## Installation Locations

When installed, files are placed in:

```
~/.local/share/hyprland-ai-automator/
├── daemon.py                        # Copied from src/
├── core/                           # Copied from src/core/
├── ai/                             # Copied from src/ai/
├── utils/                          # Copied from src/utils/
├── web/                            # Copied from src/web/
├── config_analyzer.py              # Copied from src/
├── logs/                           # Created at runtime
│   ├── daemon.log
│   ├── hyprland.log
│   └── gemini.log
└── context_db.sqlite               # Database file

~/.config/hyprland-ai-automator/
└── config.ini                      # Configuration file (chmod 600)

~/.config/systemd/user/
└── hyprland-ai-automator.service   # Systemd service file

~/.local/share/applications/
└── hyprland-ai-automator.desktop   # Desktop launcher
```

## Python Package Structure

The src/ directory can be imported as a Python package:

```python
# Main daemon
from daemon import AIAutomatorDaemon

# Core modules
from core.hyprland_connector import HyprlandConnector
from core.action_dispatcher import ActionDispatcher
from core.system_monitor import SystemMonitor
from core.context_manager import ContextManager

# AI integration
from ai.gemini_client import GeminiClient

# Utilities
from utils.config import Config
from utils.logger import setup_logger
```

## .gitignore Contents

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Logs
*.log
logs/

# Database
*.sqlite
*.db

# Configuration (sensitive)
config.ini

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
```

## Creating the ZIP Archive

To create the distributable ZIP file:

```bash
# From project root
zip -r hyprland-ai-automator.zip \
    install.sh \
    requirements.txt \
    README.md \
    LICENSE \
    src/ \
    -x "*.pyc" "*__pycache__*" "*.log" "*.sqlite"
```

## Post-Installation Directory Tree

After installation, the user's system will have:

```
$HOME/
├── .local/
│   └── share/
│       └── hyprland-ai-automator/      # Installed application
│           ├── core/
│           ├── ai/
│           ├── utils/
│           ├── web/
│           ├── daemon.py
│           ├── config_analyzer.py
│           ├── logs/
│           └── context_db.sqlite
│
└── .config/
    ├── hyprland-ai-automator/
    │   └── config.ini                   # User configuration
    │
    └── systemd/
        └── user/
            └── hyprland-ai-automator.service
```

## Development Setup

For development:

```bash
# Clone repository
git clone <repo-url>
cd hyprland-ai-automator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run directly (without installing)
cd src
python3 daemon.py
```

## Building for Distribution

To prepare for GitHub release:

1. Ensure all files are present
2. Test installation script
3. Update version numbers
4. Create release notes
5. Create ZIP archive
6. Upload to GitHub Releases