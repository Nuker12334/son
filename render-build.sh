#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Starting build process..."
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Update package list
apt-get update

# Install Chrome and dependencies
echo "Installing Chrome and dependencies..."
apt-get install -y \
    wget \
    curl \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libxss1 \
    libnss3 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libglib2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    --no-install-recommends

# Install Chrome
echo "Installing Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y google-chrome-stable

# Verify Chrome installation
echo "Chrome installation verification:"
which google-chrome || echo "Chrome not found in PATH"
google-chrome --version || echo "Chrome version check failed"

# Also check common locations
echo "Checking common Chrome locations:"
ls -la /usr/bin/google-chrome* || echo "No Chrome in /usr/bin"
ls -la /usr/bin/chromium* || echo "No Chromium in /usr/bin"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Print installed packages
echo "Installed Python packages:"
pip list

echo "Build completed successfully!"
