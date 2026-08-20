#!/bin/bash

# EC2 Environment Setup Script (Ubuntu / Amazon Linux)
# Handles Redis Setup, Python Dependencies, and Midnight Cron Job

echo "=========================================="
echo "Starting EC2 Dashboard Environment Setup"
echo "=========================================="

# 1. Detect OS and install Redis + Python dependencies
if [ -x "$(command -v apt-get)" ]; then
    echo "[*] Detected Ubuntu/Debian"
    sudo apt-get update -y
    sudo apt-get install -y redis-server python3 python3-pip cron
elif [ -x "$(command -v yum)" ]; then
    echo "[*] Detected Amazon Linux / RHEL"
    sudo yum update -y
    sudo yum install -y redis python3 python3-pip cronie
    sudo systemctl enable crond
    sudo systemctl start crond
else
    echo "[!] Unsupported OS. Please install Redis, Python3, and Pip manually."
fi

# 2. Start and Enable Redis
echo "[*] Configuring Redis..."
sudo systemctl enable redis-server || sudo systemctl enable redis
sudo systemctl start redis-server || sudo systemctl start redis

# Wait for redis to boot and test it
sleep 2
if redis-cli ping | grep -q "PONG"; then
    echo "[OK] Redis is running successfully!"
else
    echo "[!] Warning: Redis did not respond to PING."
fi

# 3. Install Python requirements
echo "[*] Installing Python dependencies (psycopg2, redis, flask)..."
pip3 install redis psycopg2-binary flask gunicorn --user

# 4. Set up the Midnight Cron Job
echo "[*] Configuring Midnight Cron Job for JSON/Redis Updates..."

# Get the absolute path to the directory where this script is running
PROJECT_DIR="$(pwd)"
CRON_SCRIPT="$PROJECT_DIR/cron_daily_state_glance.py"

# Ensure the cron script is executable
chmod +x "$CRON_SCRIPT"

# Define the cron expression (0 0 * * * = Midnight every day)
CRON_JOB="0 0 * * * /usr/bin/python3 $CRON_SCRIPT >> $PROJECT_DIR/cron_nightly.log 2>&1"

# Add to crontab if it doesn't already exist
(crontab -l 2>/dev/null | grep -F "$CRON_SCRIPT") >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[OK] Cron job already exists in crontab."
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "[OK] Added nightly cron job to run at midnight: $CRON_JOB"
fi

echo "=========================================="
echo "EC2 Setup Complete!"
echo "- Redis is installed and running."
echo "- App logic handles 'Redis -> JSON Fallback' automatically."
echo "- Cron runs $CRON_SCRIPT at Midnight."
echo "=========================================="
