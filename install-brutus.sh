#!/bin/bash

# Variables
REPO_URL="https://github.com/botsarefuture/brutus-client"
APP_DIR="/opt/brutus-client"
SERVICE_NAME="brutus-client"
PYTHON_BIN="/usr/bin/python3"
VENV_DIR="$APP_DIR/venv"
LOG_FILE="/var/log/auth.log"  # Modify based on your system
CRON_JOB="0 0 * * * $APP_DIR/update_brutus_client.sh > /var/log/brutus-client-update.log 2>&1"

# Function to check command success
check_success() {
    if [ $? -ne 0 ]; then
        echo "Error: $1 failed. Exiting."
        exit 1
    fi
}

# Step 1: Check if git and python3 are installed
command -v git >/dev/null 2>&1 || { echo "Git is not installed. Please install it."; exit 1; }
command -v $PYTHON_BIN >/dev/null 2>&1 || { echo "Python 3 is not installed. Please install it."; exit 1; }

# Step 2: Clone the repository if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    echo "Cloning the repository..."
    git clone $REPO_URL $APP_DIR
    check_success "Cloning the repository"
else
    echo "Repository already exists. Pulling latest changes..."
    cd $APP_DIR
    git pull origin main
    check_success "Pulling latest changes"
fi

# Step 3: Set up a virtual environment and install dependencies
echo "Setting up virtual environment..."
$PYTHON_BIN -m venv $VENV_DIR
check_success "Creating virtual environment"

source $VENV_DIR/bin/activate
pip install -r $APP_DIR/requirements.txt
check_success "Installing dependencies"

# Step 4: Create the systemd service file
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

# Step 5: Reload systemd, enable, and start the service
echo "Reloading systemd, enabling, and starting the service..."
sudo systemctl daemon-reload
check_success "Reloading systemd"

sudo systemctl enable $SERVICE_NAME
check_success "Enabling the service"

sudo systemctl start $SERVICE_NAME
check_success "Starting the service"

# Step 6: Check the status of the service
echo "Checking the status of the service..."
sudo systemctl status $SERVICE_NAME

# Step 7: Create or update the cron job for daily updates
(crontab -l 2>/dev/null | grep -v -F "$APP_DIR/update_brutus_client.sh"; echo "$CRON_JOB") | crontab -
check_success "Creating or updating cron job"

echo "Cron job for daily updates has been set."

echo "Brutus Client installation and setup completed successfully!"
