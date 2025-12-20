# Specter DIY Builder Bot

A Telegram bot for the Specter DIY Builder Community that automatically sends reminders for the weekly call and posts links to the YouTube recording after the call.

## Features

- **Automatic reminders** for the weekly call (Thursday 5:00 PM CET)
- **AI-powered summaries** of YouTube videos
- **Automatic posting** of the YouTube recording after the call
- **Topic management** for the next call
- **Bot commands** for manual interaction

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Displays a welcome message |
| `/status` | Displays the bot status |
| `/nextcall` | Shows information about the next call, including topics |
| `/topic <topic>` | Adds a topic to the next call |
| `/latestvideo` | Shows the latest video from the playlist with an AI summary |
| `/chatid` | Shows the chat ID (for setup) |
| `/postvideo` | Manually post the latest video |
| `/callnumber [number]` | Shows or sets the call number |

## AI Features

This bot uses Google's Gemini API to generate summaries of the YouTube videos. To enable this feature, you need to provide a Gemini API key.

1.  Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2.  Add the key to your `.env` file:
    ```
    GEMINI_API_KEY=your_gemini_api_key
    ```

If the API key is not provided, the bot will fall back to a simple summary based on the video description.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Specter-DIY-Builder-Bot.git
cd Specter-DIY-Builder-Bot
```

### 2. Set Up Python Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

1.  Copy `.env.example` to `.env`:
    ```bash
    cp .env.example .env
    ```

2.  Edit `.env` with your values:
    ```
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_CHAT_ID=your_chat_id
    GEMINI_API_KEY=your_gemini_api_key # Optional
    ```

### 4. Find the Chat ID

1.  Add the bot to the Telegram group
2.  Send `/chatid` in the group
3.  Copy the displayed ID into your `.env` file

### 5. Start the Bot

```bash
python bot.py
```


## Deployment

### Option A: Local Server / Raspberry Pi

```bash
# Run in the background with nohup
nohup python bot.py > bot.log 2>&1 &

# Or with screen
screen -S specterbot
python bot.py
# Ctrl+A, D to detach
```

### Option B: Systemd Service (Linux)

Create `/etc/systemd/system/specterbot.service`:

```ini
[Unit]
Description=Specter DIY Builder Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Specter-DIY-Builder-Bot
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable specterbot
sudo systemctl start specterbot
```

### Option C: Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

### Option D: Google Cloud Compute Engine

For GCP deployment, the bot uses the startup script in `startup-script.sh` which automatically sets up and runs the bot as a systemd service.

## Restarting the Bot

### Local Development

If you're running the bot locally (e.g., `python bot.py`):

1. Stop the current process (Ctrl+C)
2. Start it again: `python bot.py`

### Systemd Service (Linux/GCP)

If the bot is running as a systemd service:

```bash
# Restart the bot
sudo systemctl restart specterbot

# Check status
sudo systemctl status specterbot

# View logs
sudo journalctl -u specterbot -f
```

### Google Cloud Deployment

When the bot is deployed on Google Cloud Compute Engine:

**Option 1: SSH and restart (recommended)**
```bash
# SSH into the instance
gcloud compute ssh specter-bot --zone=us-west1-b

# Restart the bot service
sudo systemctl restart specterbot

# Check if it's running
sudo systemctl status specterbot
```

**Option 2: Update code and restart from local machine**
```bash
# 1. Commit and push your changes
git add .
git commit -m "Your commit message"
git push

# 2. SSH in, pull changes, and restart
gcloud compute ssh specter-bot --zone=us-west1-b --command="sudo -u botuser bash -c 'cd /home/botuser/Specter-DIY-Builder-Bot && git pull' && sudo systemctl restart specterbot"
```

**Option 3: Restart instance (if service is stuck)**
```bash
# Restart the entire VM
gcloud compute instances reset specter-bot --zone=us-west1-b
```

### After Code Changes

Whenever you modify the bot code:

1. **Local development**: Just restart the bot process
2. **Production (GCP)**:
   - Commit and push changes to GitHub
   - Pull changes on the server
   - Restart the systemd service

Example workflow:
```bash
# Local: Make changes, test, commit
git add bot.py
git commit -m "fix: improve /nextcall output"
git push

# Deploy to GCP
gcloud compute ssh specter-bot --zone=us-west1-b --command="sudo -u botuser bash -c 'cd /home/botuser/Specter-DIY-Builder-Bot && git pull' && sudo systemctl restart specterbot"
```

## Customization

### Change Schedule

In `config.py`, you can adjust the following values:

```python
CALL_DAY = "thursday"  # Day of the call
CALL_HOUR = 17         # Hour (24h format)
TIMEZONE = "Europe/Berlin"
```

### Customize Messages

You can also find the message templates in `config.py`:
- `REMINDER_MESSAGE_3_DAYS`
- `REMINDER_MESSAGE_1_DAY`
- `REMINDER_MESSAGE_1_HOUR`
- `POST_CALL_MESSAGE_TEMPLATE`

## Project Structure

```
Specter-DIY-Builder-Bot/
├── bot.py              # Main bot with scheduler
├── config.py           # Configuration and messages
├── youtube_utils.py    # YouTube API integration
├── requirements.txt    # Python dependencies
├── .env.example        # Example configuration
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Troubleshooting

### Bot is not responding
- Check if the bot token is correct
- Make sure the bot has been added to the group
- Check the logs: `tail -f bot.log`

### Reminders are not being sent
- Check if the `TELEGRAM_CHAT_ID` is correct
- Make sure the bot has admin rights in the group (or at least permission to send messages)

### YouTube videos are not found
- Check the `YOUTUBE_PLAYLIST_ID` in the `.env`
- Test with `python youtube_utils.py`

## License

MIT License

## Contact

Specter DIY Builder Community - [Telegram Group](https://t.me/+93YQ5guL95syMmYy)