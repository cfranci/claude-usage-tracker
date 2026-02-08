#!/bin/bash
#
# Claude Usage Tracker - Installation Script
#
# This script sets up the Claude Usage Tracker menu bar app.
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
LAUNCH_AGENT_PLIST="$LAUNCH_AGENT_DIR/com.claude-usage-tracker.plist"

echo "================================================"
echo "   Claude Usage Tracker - Installation"
echo "================================================"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

# Activate and install dependencies
echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q

echo "Dependencies installed successfully."

# Make tracker.py executable
chmod +x "$SCRIPT_DIR/tracker.py"

# Ask about API key
echo ""
echo "================================================"
echo "   API Key Setup"
echo "================================================"
echo ""
echo "You need an Admin API key from Anthropic to use this app."
echo "Get one from: https://console.anthropic.com/settings/admin-keys"
echo ""
read -p "Would you like to set up your API key now? (y/n): " setup_key

if [[ "$setup_key" =~ ^[Yy]$ ]]; then
    echo ""
    read -sp "Enter your Admin API key: " api_key
    echo ""

    if [ -n "$api_key" ]; then
        # Store in macOS Keychain
        security delete-generic-password -s "claude-usage-tracker" -a "admin-api-key" 2>/dev/null || true
        security add-generic-password -s "claude-usage-tracker" -a "admin-api-key" -w "$api_key"
        echo "API key stored securely in macOS Keychain."
    fi
fi

# Ask about auto-start
echo ""
echo "================================================"
echo "   Auto-Start Setup"
echo "================================================"
echo ""
read -p "Would you like to start the app automatically at login? (y/n): " auto_start

if [[ "$auto_start" =~ ^[Yy]$ ]]; then
    mkdir -p "$LAUNCH_AGENT_DIR"

    cat > "$LAUNCH_AGENT_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-usage-tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$SCRIPT_DIR/tracker.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/claude-usage-tracker.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/claude-usage-tracker.log</string>
</dict>
</plist>
EOF

    echo "Launch agent created at: $LAUNCH_AGENT_PLIST"
    echo "The app will start automatically at next login."
fi

# Done
echo ""
echo "================================================"
echo "   Installation Complete!"
echo "================================================"
echo ""
echo "To start the app now, run:"
echo "  cd $SCRIPT_DIR && ./venv/bin/python tracker.py"
echo ""
echo "Or if you enabled auto-start, just log out and back in."
echo ""

# Ask to start now
read -p "Would you like to start the app now? (y/n): " start_now

if [[ "$start_now" =~ ^[Yy]$ ]]; then
    echo "Starting Claude Usage Tracker..."
    cd "$SCRIPT_DIR"
    nohup "$VENV_DIR/bin/python" tracker.py > /dev/null 2>&1 &
    echo "App started! Look for it in your menu bar."
fi

echo ""
echo "Done!"
