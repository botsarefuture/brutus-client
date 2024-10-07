#!/bin/bash

# Update script for brutus-client

# Define the installation directory
INSTALL_DIR="/opt/brutus-client"

# Navigate to the installation directory
cd "$INSTALL_DIR" || { echo "Failed to navigate to $INSTALL_DIR"; exit 1; }

# Fetch the latest version from the GitHub repository
echo "Fetching the latest version of brutus-client..."
git fetch origin

# Checkout the latest version
git checkout main
git pull origin main

# Install/update required dependencies
echo "Installing/updating dependencies..."
pip install -r requirements.txt

echo "Update complete!"
