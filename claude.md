# Specter DIY Builder Bot - Claude Code Reference

## Project Summary

This is a **Telegram bot for the Specter DIY Builder Community** that automates community management by sending scheduled reminders for the weekly Thursday 17:00 CET call and automatically posting YouTube recording links with AI-generated summaries after each call. The bot uses APScheduler for scheduling, integrates with Telegram Bot API, YouTube (yt-dlp), Google Gemini AI for summaries, and can be deployed on Google Cloud Compute Engine.

## Quick Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Group                           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │   bot.py           │  Main application entry point
        │ - Command handlers │  - 9 Telegram commands
        │ - Scheduler setup  │  - Reminder scheduling
        │ - Video posting    │  - State management
        └────┬──────────────┬┘
             │              │
        ┌────▼─────┐   ┌───▼──────────┐
        │config.py │   │youtube_utils.│
        │          │   │    py        │
        │ - Config │   │              │
        │ - State  │   │ - yt-dlp     │
        │ - Msgs   │   │ - Gemini AI  │
        └──────────┘   └──────────────┘
             │              │
        ┌────▼──────────────▼──┐
        │ call_state.json      │
        │ (persistent state)   │
        └──────────────────────┘
```

## Key Files Quick Reference

| File | Purpose |
|------|---------|
| **bot.py** | Main application - command handlers, scheduler, reminder/video posting logic |
| **config.py** | Configuration loading, state management (call_state.json), German message templates |
| **youtube_utils.py** | YouTube playlist extraction via yt-dlp, AI summarization via Google Gemini |
| **startup-script.sh** | Google Cloud Compute Engine deployment automation (GCP metadata integration) |
| **call_state.json** | Runtime state file storing call_number and topics list |
| **.env** | Environment variables (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY) |
| **requirements.txt** | Python dependencies |

## Development Context - Important Facts

**Language Duality**: Code is written in English, but all user-facing messages are in German.

**State Persistence**: Call number and topics are stored in `call_state.json` (not a database). This file:
- Defaults to `{"call_number": 9, "topics": []}`
- Gets updated when videos are posted (call number incremented)
- Gets reset for topics after each call
- Lives in the same directory as bot.py

**Scheduling Model**: APScheduler with AsyncIOScheduler in Europe/Berlin timezone:
- Uses date-based triggers (one-time jobs that recalculate when bot restarts)
- Reminders scheduled 72h, 24h, and 1h before Thursday 17:00 CET
- Video check scheduled for next day at 12:00 noon

**Duplicate Prevention**: Bot tracks `last_posted_video_id` in memory to avoid re-posting the same video.

**Async/Await Pattern**: All message sending and API calls use async/await via python-telegram-bot.

## Message Formatting (HTML Links)

**Important**: All bot messages use HTML formatting mode for clickable text links.

### HTML Link Syntax
```python
# Correct way to create clickable links in Telegram
parse_mode=ParseMode.HTML
message = '<a href="https://example.com">Click Here</a>'
```

### Key Rules
1. **Always use HTML mode**: `parse_mode=ParseMode.HTML`
2. **Link syntax**: `<a href="URL">text</a>` - text becomes clickable
3. **Escape HTML characters**: Use `&lt;` for `<` and `&gt;` for `>`
4. **Disable previews**: `disable_web_page_preview=True` to hide URL cards
5. **Don't use MARKDOWN_V2**: It has complex escaping and doesn't work reliably with links

### Example Template
```python
REMINDER_MESSAGE = """
📅 <a href="{calendar_link}">Calendar</a>
🔗 <a href="{jitsi_link}">Jitsi</a>
"""
```

### Where Links Are Used
- `/nextcall` command (bot.py line 325-326)
- All reminder messages (config.py lines 128-129, 142-143, 154-155)
- Reminder sending function (bot.py line 163)

## Common Development Tasks

### Where to modify...

- **Message templates** → `config.py` (lines 83-143)
- **Bot commands** → `bot.py` command handler functions (lines 151-314)
- **Scheduled tasks** → `setup_scheduler()` function in `bot.py` (lines 317-355)
- **YouTube playlist/channel** → `config.py` YOUTUBE_PLAYLIST_ID and YOUTUBE_CHANNEL_ID
- **Call timing** → `config.py` CALL_HOUR, CALL_MINUTE, REMINDERS array
- **AI summarization prompt** → `youtube_utils.py` prompt text (lines 28-32)
- **Timezone** → `config.py` TIMEZONE setting

### Adding a new command

1. Create async handler function in `bot.py`
2. Register with `application.add_handler(CommandHandler("command_name", handler_function))`
3. Update /help text to include the new command

### Testing YouTube integration

Run standalone: `python youtube_utils.py` - fetches latest video and generates summary without needing Telegram.

## Integration Points

### Telegram Bot API (python-telegram-bot v21.7)
- Polling mode (not webhooks)
- Bot token from @BotFather
- Chat ID for target group/channel
- Markdown formatting for messages

### YouTube Integration (yt-dlp)
- Playlist: `PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm`
- Channel: `UCs_tO31-N62qAD_S7s_H-8w`
- Extracts: video_id, title, url, description, upload_date, duration
- Error handling: Returns None if fetch fails

### Google Gemini AI (google-generativeai v0.8.5)
- Model: `gemini-pro`
- Purpose: German-language summaries of video descriptions
- Fallback: If no API key, uses first 500 chars of description
- Error handling: Returns truncated description if API fails

### Google Cloud Platform
- Compute Engine VM instances
- Metadata service for secrets (telegram-bot-token, telegram-chat-id)
- Startup script creates systemd service for auto-start
- Service runs as dedicated `botuser` account

## State Management Details

### call_state.json Schema
```json
{
  "call_number": 10,
  "topics": [
    "PR review process",
    "New feature discussion"
  ]
}
```

### Operations
- **Load**: `load_call_state()` - reads file or returns defaults
- **Save**: `save_call_state(state)` - writes to file
- **Get number**: `get_next_call_number()` - reads current number
- **Increment**: `increment_call_number()` - increments number AND resets topics

## Deployment - GCP Overview

The `startup-script.sh` handles complete deployment:
1. Installs Python 3 and dependencies
2. Clones repository (or pulls updates)
3. Creates `botuser` system account
4. Sets up Python virtual environment
5. Fetches secrets from GCP metadata service
6. Creates .env file with Telegram credentials
7. Creates systemd service for auto-restart
8. Enables and starts the service

**Secrets Fetching**: Bot fetches `telegram-bot-token` and `telegram-chat-id` from GCP instance metadata (requires these to be set as instance attributes).

**Service Management**: Created as `/etc/systemd/system/specterbot.service` - uses journal logging, auto-restart on failure.

## Key Dependencies

```
python-telegram-bot==21.7      # Telegram API
apscheduler==3.10.4            # Scheduling
yt-dlp==2024.11.18            # YouTube extraction
google-generativeai==0.8.5    # Gemini AI
python-dotenv==1.0.1          # .env loading
pytz==2024.2                  # Timezone handling
```

## Logging

- Logger: `logging.basicConfig()` configured in bot.py (lines 25-28)
- Output: stdout (captured by systemd journal in GCP deployment)
- Level: INFO (logs scheduler jobs, sent messages, errors)
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

## Common Issues When Modifying

1. **Async/await**: All message sends must use `await bot.send_message()` or `await update.message.reply_text()`
2. **Timezone**: Always use `pytz.timezone(Config.TIMEZONE)` when working with times
3. **State races**: `save_call_state()` writes synchronously - keep state operations short
4. **Message formatting**: Use Markdown with `parse_mode=ParseMode.MARKDOWN`
5. **German templates**: Messages use German with emoji - maintain this style when editing

## Running Locally

```bash
# Setup
python -m venv venv
venv\Scripts\activate  # Windows: activate, Linux: source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env with your bot token and chat ID

# Run
python bot.py
```

## For Detailed Technical Information

See `TECHNICAL_DOCS.md` for comprehensive documentation including:
- Complete data flow diagrams
- Detailed API integration documentation
- Message template formats
- Error handling strategies
- Troubleshooting guide
- All configuration options explained
