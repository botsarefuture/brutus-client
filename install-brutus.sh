#!/bin/bash

# Variables
REPO_URL="https://github.com/botsarefuture/brutus-client"
APP_DIR="/opt/brutus-client"
SERVICE_NAME="brutus-client"
PYTHON_BIN="/usr/bin/python3"
VENV_DIR="$APP_DIR/venv"
LOG_FILE="/var/log/auth.log"  # Modify based on your system

# Step 1: Clone the repository
echo "Cloning the repository..."
git clone $REPO_URL $APP_DIR

# Step 2: Set up a virtual environment and install dependencies
echo "Setting up virtual environment..."
$PYTHON_BIN -m venv $VENV_DIR
source $VENV_DIR/bin/activate
pip install -r $APP_DIR/requirements.txt

# Step 3: Create the systemd service file
echo "Creating systemd service file..."

cat << EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Brutus Client - SSH Brute Force Protection
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/index.py
Restart=always
Environment="PATH=$VENV_DIR/bin"
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

# Step 4: Reload systemd, enable, and start the service
echo "Reloading systemd, enabling, and starting the service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

# Step 5: Check the status of the service
echo "Checking the status of the service..."
sudo systemctl status $SERVICE_NAME
