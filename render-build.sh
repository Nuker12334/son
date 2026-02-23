#!/usr/bin/env bash
set -o errexit

echo "Installing Chromium instead of Chrome..."

# Install Chromium (lighter weight)
apt-get update
apt-get install -y chromium chromium-driver

# Create symlink for google-chrome (some scripts expect this)
ln -s /usr/bin/chromium /usr/bin/google-chrome || true

# Verify
chromium --version
which chromium

pip install -r requirements.txt
