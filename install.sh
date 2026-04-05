#!/bin/bash

# Pi Solar Monitor Installation Script
# This script installs dependencies, initializes the database, and sets up the systemd service.

set -e

echo "-------------------------------------------------------"
echo "☀️  Pi Solar Monitor Installation"
echo "-------------------------------------------------------"
echo "This script will:"
echo "1. Check for Python 3.9+"
echo "2. Install Python dependencies (from requirements.txt)"
echo "3. Initialize the SQLite database (if it doesn't exist)"
echo "4. Create and install a systemd service (pi-solar.service)"
echo "-------------------------------------------------------"

read -p "Do you want to continue? (y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Installation aborted."
    exit 0
fi

# 1. Check Python Version
echo "Checking Python version..."
PYTHON_BIN=$(which python3)
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Error: python3 not found. Please install Python 3.9 or higher."
    exit 1
fi

PY_VERSION=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJOR=$(echo $PY_VERSION | cut -d. -f1)
MINOR=$(echo $PY_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]); then
    echo "❌ Error: Python 3.9 or higher is required. Found version $PY_VERSION."
    exit 1
fi
echo "✅ Python $PY_VERSION found."

# 2. Install Python Dependencies
INSTALL_CMD="$PYTHON_BIN -m pip install -r requirements.txt"
VENV_PATH=""

# Detect externally managed environment (PEP 668)
IS_MANAGED=$($PYTHON_BIN -c 'import sys; import os; print(any(os.path.exists(os.path.join(p, "EXTERNALLY-MANAGED")) for p in sys.path))' 2>/dev/null || echo "False")

if [ "$IS_MANAGED" == "True" ]; then
    echo "⚠️  Detected an externally managed Python environment (e.g., Debian/Ubuntu)."
    echo "How would you like to install dependencies?"
    echo "1) Create a virtual environment (Recommended)"
    echo "2) Use --break-system-packages"
    read -p "Select an option (1/2): " dep_choice

    if [ "$dep_choice" == "1" ]; then
        read -p "Enter the path for the virtual environment (default: .venv): " VENV_PATH
        VENV_PATH=${VENV_PATH:-.venv}
        # Ensure VENV_PATH is absolute
        if [[ "$VENV_PATH" != /* ]]; then
            VENV_PATH="$(pwd)/$VENV_PATH"
        fi
        echo "Creating virtual environment at $VENV_PATH..."
        $PYTHON_BIN -m venv "$VENV_PATH"
        PYTHON_BIN="$VENV_PATH/bin/python3"
        INSTALL_CMD="$PYTHON_BIN -m pip install -r requirements.txt"
    elif [ "$dep_choice" == "2" ]; then
        INSTALL_CMD="$PYTHON_BIN -m pip install -r requirements.txt --break-system-packages"
    else
        echo "Invalid choice. Aborting."
        exit 1
    fi
else
    # Not externally managed, but maybe user wants a venv anyway?
    read -p "Would you like to use a virtual environment? (y/N): " venv_confirm
    if [[ $venv_confirm =~ ^[Yy]$ ]]; then
        read -p "Enter the path for the virtual environment (default: .venv): " VENV_PATH
        VENV_PATH=${VENV_PATH:-.venv}
        # Ensure VENV_PATH is absolute
        if [[ "$VENV_PATH" != /* ]]; then
            VENV_PATH="$(pwd)/$VENV_PATH"
        fi
        echo "Creating virtual environment at $VENV_PATH..."
        $PYTHON_BIN -m venv "$VENV_PATH"
        PYTHON_BIN="$VENV_PATH/bin/python3"
        INSTALL_CMD="$PYTHON_BIN -m pip install -r requirements.txt"
    fi
fi

echo "Installing dependencies..."
$INSTALL_CMD

# 3. Initialize Database
echo "Checking database..."
DB_PATH="data/inverter_logs.db"
if [ -f "$DB_PATH" ]; then
    echo "⚠️  Warning: Database already exists at $DB_PATH."
    echo "   Skipping initialization to avoid data loss."
    echo "   Ensure your schema is up to date."
else
    echo "Initializing database..."
    $PYTHON_BIN init_db.py
fi

# 4. Systemd Service Setup
echo "-------------------------------------------------------"
echo "Systemd Service Setup"
echo "-------------------------------------------------------"

CURRENT_USER=$(whoami)
read -p "Enter the user to run the service as (default: $CURRENT_USER): " SERVICE_USER
SERVICE_USER=${SERVICE_USER:-$CURRENT_USER}

WORKING_DIR=$(pwd)
read -p "Enter the working directory (default: $WORKING_DIR): " SERVICE_DIR
SERVICE_DIR=${SERVICE_DIR:-$WORKING_DIR}

SERVICE_FILE="/etc/systemd/system/pi-solar.service"

echo "Generating pi-solar.service..."

cat <<EOF > pi-solar.service
[Unit]
Description=Pi Solar Monitor Service
After=network.target

[Service]
User=$SERVICE_USER
WorkingDirectory=$SERVICE_DIR
ExecStart=$PYTHON_BIN main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "To install the service, sudo privileges are required."
sudo mv pi-solar.service "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable pi-solar.service
sudo systemctl start pi-solar.service

echo "-------------------------------------------------------"
echo "✅ Installation Complete!"
echo "-------------------------------------------------------"
echo "The Pi Solar Monitor service is now running."
echo "You can check the status with: sudo systemctl status pi-solar.service"
echo "The dashboard is available at http://$(hostname -I | awk '{print $1}'):8000"
echo "-------------------------------------------------------"
