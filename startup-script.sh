#!/bin/bash
# Startup script for Specter DIY Builder Bot on Google Cloud Compute Engine

set -e

# Install dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Create bot user
useradd -m -s /bin/bash botuser || true

# Clone or update repository
cd /home/botuser
if [ -d "Specter-DIY-Builder-Bot" ]; then
    cd Specter-DIY-Builder-Bot
    git pull
else
    git clone https://github.com/Schnuartz/Specter-DIY-Builder-Bot.git
    cd Specter-DIY-Builder-Bot
fi

# Create virtual environment and install dependencies
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Create .env file from instance metadata
TELEGRAM_BOT_TOKEN=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/telegram-bot-token" -H "Metadata-Flavor: Google")
TELEGRAM_CHAT_ID=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/telegram-chat-id" -H "Metadata-Flavor: Google")
GEMINI_API_KEY=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/gemini-api-key" -H "Metadata-Flavor: Google")

cat > .env << EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
YOUTUBE_PLAYLIST_ID=PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm
GEMINI_API_KEY=${GEMINI_API_KEY}
EOF

# Set ownership
chown -R botuser:botuser /home/botuser/Specter-DIY-Builder-Bot

# Create systemd service
cat > /etc/systemd/system/specterbot.service << 'EOF'
[Unit]
Description=Specter DIY Builder Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/Specter-DIY-Builder-Bot
ExecStart=/home/botuser/Specter-DIY-Builder-Bot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable specterbot
systemctl start specterbot

echo "Specter DIY Builder Bot started successfully!"
