# Specter DIY Builder Bot

A Telegram bot for the Specter DIY Builder Community that automatically sends reminders for the weekly call and posts links to the YouTube recording after the call.

## Features

- **Automatic reminders** for the weekly call (Thursday 5:00 PM CET)
  - 3 days in advance (Monday)
  - 1 day in advance (Wednesday)
  - 1 hour in advance (Thursday)
- **Automatic posting** of the YouTube recording after the call
- **Summary** extracted from the video description
- **Bot commands** for manual interaction

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Displays a welcome message |
| `/status` | Displays the bot status |
| `/nextcall` | Shows the next call date |
| `/latestvideo` | Shows the latest video from the playlist |
| `/chatid` | Shows the chat ID (for setup) |
| `/postvideo` | Manually post the latest video |

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/FinnFrei662/Specter-DIY-Builder-Bot.git
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

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

### 4. Find the Chat ID

1. Add the bot to the Telegram group
2. Send `/chatid` in the group
3. Copy the displayed ID into your `.env` file

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