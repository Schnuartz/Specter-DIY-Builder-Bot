# Specter DIY Builder Bot - Technical Documentation

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Data Flow and Sequences](#data-flow-and-sequences)
3. [APScheduler Configuration](#apscheduler-configuration)
4. [API Integrations](#api-integrations)
5. [State Management](#state-management)
6. [Bot Commands Reference](#bot-commands-reference)
7. [Message Templates](#message-templates)
8. [Configuration and Environment](#configuration-and-environment)
9. [Google Cloud Deployment](#google-cloud-deployment)
10. [Error Handling](#error-handling)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)

---

## System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Telegram Network                             │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 │ Polling
                 ▼
        ┌─────────────────────────────┐
        │   python-telegram-bot       │
        │   (Application.builder)     │
        └──┬──────────────────────┬───┘
           │                      │
           │ Command Handlers     │ Bot Instance
           ▼                      ▼
    ┌──────────────────┐  ┌──────────────────┐
    │ bot.py           │  │ Async I/O Loop   │
    │ - Command funcs  │  │                  │
    │ - Scheduler      │  │ APScheduler      │
    │ - Message format │  │ (TimerScheduler) │
    └────────┬─────────┘  └─────────┬────────┘
             │                      │
             ├─────┬────────────────┤
             │     │                │
             ▼     ▼                ▼
       ┌──────┐ ┌──────────┐ ┌──────────────────┐
       │State │ │ YouTube  │ │ Google Gemini    │
       │Mgmt  │ │ (yt-dlp) │ │ AI               │
       │      │ │          │ │                  │
       │config│ │youtube_  │ │ google-           │
       │.py   │ │utils.py  │ │ generativeai     │
       └──┬───┘ └────┬─────┘ └────────┬─────────┘
          │          │                │
          ▼          ▼                ▼
    ┌──────────┐ ┌──────────┐ ┌──────────────┐
    │.env      │ │YouTube   │ │ GCP          │
    │config    │ │Playlist  │ │ Credentials  │
    └──────────┘ └──────────┘ └──────────────┘
          │
          ▼
    ┌──────────────────────┐
    │ call_state.json      │
    │ {                    │
    │   call_number: int   │
    │   topics: [strings]  │
    │ }                    │
    └──────────────────────┘
```

### Component Responsibilities

**bot.py** (394 lines)
- Entry point and main application
- Telegram command handlers (9 commands)
- Scheduler initialization and job setup
- Message formatting and sending
- Integration orchestration
- Logging configuration

**config.py** (158 lines)
- Environment variable loading (.env parsing)
- State file management (JSON read/write)
- Configuration validation
- Message template definitions (5 templates in German)
- Constants for schedule, timezone, links

**youtube_utils.py** (159 lines)
- YouTube playlist/video data extraction (yt-dlp)
- VideoInfo dataclass for type safety
- AI summarization orchestration (Gemini API)
- Error handling for API calls
- Standalone testing capability

**call_state.json** (Runtime)
- Persistent storage of application state
- Call counter (incremented after each recording posted)
- Topics list (reset after each call)
- Location: Same directory as bot.py

---

## Data Flow and Sequences

### 1. Application Startup Sequence

```
main()
  ├─ Config.validate(require_chat_id=False)
  │   └─ Check TELEGRAM_BOT_TOKEN exists
  │
  ├─ Application.builder().token(token).build()
  │   └─ Initialize telegram.ext.Application
  │
  ├─ Register 9 CommandHandlers
  │   ├─ /start → start_command()
  │   ├─ /help → help_command()
  │   ├─ /status → status_command()
  │   ├─ /nextcall → nextcall_info_command()
  │   ├─ /topic → topic_command()
  │   ├─ /latestvideo → latest_video_command()
  │   ├─ /chatid → chatid_command()
  │   ├─ /callnumber → callnumber_command()
  │   └─ /postvideo → post_video_command()
  │
  ├─ Config.is_fully_configured() check
  │   └─ If true: setup_scheduler(application.bot)
  │       ├─ Get next Thursday 17:00 CET
  │       ├─ Schedule 3-day reminder (72h before)
  │       ├─ Schedule 1-day reminder (24h before)
  │       ├─ Schedule 1-hour reminder (1h before)
  │       └─ Schedule video check (next day 12:00)
  │   └─ If false: Log "SETUP MODE" (awaiting /chatid)
  │
  └─ application.run_polling()
      └─ Start event loop, listen for updates
```

### 2. Reminder Sending Flow

```
Scheduler Trigger (72h, 24h, or 1h before call)
  │
  ├─ send_3_day_reminder() / send_1_day_reminder() / send_1_hour_reminder()
  │   │
  │   └─ send_reminder(bot, Config.REMINDER_MESSAGE_X)
  │       │
  │       ├─ load_call_state()
  │       │   └─ Read call_state.json → dict
  │       │
  │       ├─ Extract topics from state
  │       │
  │       ├─ format_message(template, topics)
  │       │   ├─ Get next_call_number()
  │       │   ├─ Get next_thursday() time
  │       │   ├─ Format topics as bullet list
  │       │   └─ Replace template placeholders
  │       │
  │       └─ await bot.send_message(
  │           chat_id=TELEGRAM_CHAT_ID,
  │           text=formatted_message,
  │           parse_mode=ParseMode.MARKDOWN
  │       )
  │
  └─ Log success/failure
```

### 3. Video Posting Flow

```
Scheduler Trigger (day after call, 12:00 noon) OR /postvideo command
  │
  └─ check_and_post_new_video(bot)
      │
      ├─ get_latest_video_from_playlist(YOUTUBE_PLAYLIST_ID)
      │   │
      │   ├─ Build playlist URL
      │   │   └─ f"https://www.youtube.com/playlist?list={playlist_id}"
      │   │
      │   ├─ Configure yt_dlp options
      │   │   ├─ quiet=True, no_warnings=True
      │   │   ├─ extract_flat=False (get full details)
      │   │   └─ playlistend=1 (only first/latest video)
      │   │
      │   ├─ Extract info via yt_dlp.YoutubeDL()
      │   │   └─ Return VideoInfo(video_id, title, url, description, upload_date, duration)
      │   │
      │   └─ On error: log and return None
      │
      ├─ If video is None: log warning and return
      │
      ├─ Check if video.video_id == last_posted_video_id
      │   └─ If yes: log "already posted" and return (duplicate prevention)
      │
      ├─ Get current call_number (before incrementing)
      │   └─ get_next_call_number()
      │
      ├─ Access video.summary
      │   └─ Triggers @property summary which calls:
      │       │
      │       └─ summarize_with_ai(video.description)
      │           │
      │           ├─ Check if GEMINI_API_KEY configured
      │           │   └─ If not: return truncated description (first 500 chars)
      │           │
      │           ├─ genai.configure(api_key=GEMINI_API_KEY)
      │           │
      │           ├─ Create genai.GenerativeModel('gemini-pro')
      │           │
      │           ├─ Create prompt asking for German summary
      │           │   └─ "Summarize...in German...3-4 bullet points"
      │           │
      │           ├─ model.generate_content(prompt)
      │           │
      │           └─ On error: return truncated description
      │
      ├─ Format POST_CALL_MESSAGE_TEMPLATE
      │   └─ Replace {call_number}, {title}, {summary}, {url}
      │
      ├─ Send message
      │   └─ await bot.send_message(
      │       chat_id=TELEGRAM_CHAT_ID,
      │       text=formatted_message,
      │       parse_mode=ParseMode.MARKDOWN,
      │       disable_web_page_preview=False (show YouTube thumbnail)
      │   )
      │
      ├─ Update last_posted_video_id
      │   └─ last_posted_video_id = video.video_id
      │
      ├─ Increment call number AND reset topics
      │   └─ increment_call_number()
      │       ├─ load_call_state()
      │       ├─ state["call_number"] += 1
      │       ├─ state["topics"] = []
      │       ├─ save_call_state(state)
      │       └─ return new_number
      │
      └─ Log success
```

### 4. Topic Addition Flow

```
User sends: /topic "New PR review process"
  │
  └─ topic_command(update, context)
      │
      ├─ Extract topic text from context.args
      │   └─ " ".join(context.args)
      │
      ├─ Validate topic not empty
      │   └─ If empty: reply with usage help and return
      │
      ├─ Load current state
      │   └─ load_call_state()
      │
      ├─ Append topic to topics list
      │   ├─ topics = state.get("topics", [])
      │   ├─ topics.append(topic)
      │   └─ state["topics"] = topics
      │
      ├─ Save updated state
      │   └─ save_call_state(state)
      │
      └─ Reply to user with confirmation
          └─ "✅ Topic added: \"{topic}\""
```

---

## APScheduler Configuration

### Scheduler Setup Details

Located in `setup_scheduler()` function (lines 317-355 in bot.py).

**Scheduler Type**: AsyncIOScheduler
- Integrates with asyncio event loop used by python-telegram-bot
- Timezone: Europe/Berlin (CET/CEST aware)
- Manages async job execution

### Job Scheduling

**Next Thursday Calculation**:
```python
def get_next_thursday() -> datetime:
    tz = pytz.timezone(Config.TIMEZONE)  # Europe/Berlin
    now = datetime.now(tz)

    days_until_thursday = (3 - now.weekday()) % 7
    # weekday(): 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday
    # If today is Thursday and >= 17:00, next call is in 7 days
    if days_until_thursday == 0 and now.hour >= 17:
        days_until_thursday = 7

    next_call = now.replace(hour=17, minute=0, second=0, microsecond=0)
    next_call += timedelta(days=days_until_thursday)
    return next_call
```

**Scheduled Jobs**:

1. **3-Day Reminder**
   - ID: `reminder_72h`
   - Trigger: date (one-time)
   - Run date: next_thursday - 72 hours
   - Function: send_3_day_reminder(bot)
   - Message: REMINDER_MESSAGE_3_DAYS

2. **1-Day Reminder**
   - ID: `reminder_24h`
   - Trigger: date (one-time)
   - Run date: next_thursday - 24 hours
   - Function: send_1_day_reminder(bot)
   - Message: REMINDER_MESSAGE_1_DAY (includes topics)

3. **1-Hour Reminder**
   - ID: `reminder_1h`
   - Trigger: date (one-time)
   - Run date: next_thursday - 1 hour
   - Function: send_1_hour_reminder(bot)
   - Message: REMINDER_MESSAGE_1_HOUR (with YouTube livestream link)

4. **Video Check**
   - ID: `video_check`
   - Trigger: date (one-time)
   - Run date: next_thursday + 1 day, 12:00 noon
   - Function: check_and_post_new_video(bot)
   - Purpose: Post latest YouTube recording with summary

**Job Recalculation**: Each job is a one-time date trigger. On bot restart, `setup_scheduler()` recalculates next Thursday and reschedules all jobs. This means:
- Bot can be restarted without missing scheduled reminders
- Reminders adapt if bot is down temporarily
- No persistent scheduler state needed (stateless design)

### Logging Scheduled Jobs

After scheduling, bot logs all jobs:
```python
for job in scheduler.get_jobs():
    logger.info(f"Scheduled job: {job.name} at {job.next_run_time}")
```

Example output:
```
Scheduled job: 3h reminder at 2024-12-22 13:00:00+01:00
Scheduled job: 1h reminder at 2024-12-25 16:00:00+01:00
Scheduled job: 1h reminder at 2024-12-25 16:00:00+01:00
Scheduled job: Video check at 2024-12-26 12:00:00+01:00
```

---

## API Integrations

### 1. Telegram Bot API (python-telegram-bot v21.7)

**Purpose**: Send messages to Telegram group/channel, receive commands

**Authentication**:
- Bot token from @BotFather (Telegram bot platform)
- Stored in environment variable: `TELEGRAM_BOT_TOKEN`

**Chat ID**:
- Target group/channel identifier
- Can be positive (user) or negative (group)
- Obtained via `/chatid` command
- Stored in environment variable: `TELEGRAM_CHAT_ID`

**Modes**:
- Polling: Bot periodically asks Telegram "any new messages?"
- Preferred over webhooks for reliability and simplicity
- Integrated with asyncio event loop

**Key Methods Used**:
```python
# Send message to configured chat
await bot.send_message(
    chat_id=TELEGRAM_CHAT_ID,
    text="Message content",
    parse_mode=ParseMode.MARKDOWN,  # Enable markdown formatting
    disable_web_page_preview=True|False  # Control link previews
)

# Reply to user
await update.message.reply_text(
    "Response text",
    parse_mode=ParseMode.MARKDOWN
)
```

**Markdown Support**:
- `*bold*` → **bold**
- `_italic_` → *italic*
- `` `code` `` → monospace
- `[link text](url)` → clickable link

**Rate Limiting**: None explicitly handled in code; Telegram has built-in rate limiting (~30 messages/second).

### 2. YouTube Integration (yt-dlp v2024.11.18)

**Purpose**: Extract metadata from YouTube videos and playlists

**Libraries**: yt-dlp (modern fork of youtube-dl)

**Playlist Target**:
- Playlist ID: `PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm`
- Channel ID: `UCs_tO31-N62qAD_S7s_H-8w`
- Both configurable via `.env`

**Extraction Process**:
```python
def get_latest_video_from_playlist(playlist_id: str) -> Optional[VideoInfo]:
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    ydl_opts = {
        "quiet": True,           # Suppress yt-dlp output
        "no_warnings": True,     # No warning messages
        "extract_flat": False,   # Get full video details (not just IDs)
        "playlistend": 1,        # Only extract first (latest) video
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(playlist_url, download=False)
        # result["entries"] contains list of videos
        # entries[0] is the most recent video
```

**Data Extracted**:
```python
@dataclass
class VideoInfo:
    video_id: str           # "dQw4w9WgXcQ"
    title: str              # "Video Title"
    url: str                # "https://youtube.com/watch?v=..."
    description: str        # Full video description
    upload_date: str        # "20241219" (YYYYMMDD)
    duration: int           # Seconds
```

**Error Handling**:
- yt-dlp exceptions caught and logged
- Returns None if extraction fails
- Graceful degradation (no crash on network error)

### 3. Google Gemini AI (google-generativeai v0.8.5)

**Purpose**: Generate German-language summaries of video descriptions

**Model**: `gemini-pro` (text-only model)

**API Key**:
- Obtained from: [Google AI Studio](https://aistudio.google.com/app/apikey)
- Optional configuration - bot works without it (fallback to truncated description)
- Stored in: `GEMINI_API_KEY` environment variable

**Summarization Process**:
```python
def summarize_with_ai(text: str) -> str:
    if not text:
        return "No content available to summarize."

    if not Config.GEMINI_API_KEY:
        # Fallback: return truncated description
        return text[:500].strip() + "..." if len(text) > 500 else text

    try:
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        prompt = """You are a helpful assistant...
        Your task is to summarize...video about a technical community call.
        The summary should be concise, in German, and highlight main topics.
        Focus on technical aspects, pull requests, new features.
        Maximum 3-4 bullet points.

        Please summarize this: {text}"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        # Fallback on error
        return text[:500].strip() + "..." if len(text) > 500 else text
```

**Output Format**: German bullet points (expected format)
```
• Neue PRs wurden diskutiert
• Performance-Optimierungen implementiert
• Deployment-Prozess verbessert
```

**Rate Limits**:
- Gemini API has quota limits
- Error gracefully if limit exceeded (falls back to truncated description)
- Not a blocker if API is down

**Cost**: Google Gemini Pro API is free tier (quota-limited).

### 4. Google Cloud Platform (GCP)

**Service**: Compute Engine (VM instances)

**Deployment via Startup Script**:
```bash
#!/bin/bash
# startup-script.sh handles:
1. apt-get update && apt-get install python3 python3-pip python3-venv git
2. useradd -m -s /bin/bash botuser
3. git clone repo || git pull
4. python3 -m venv venv
5. venv/bin/pip install -r requirements.txt
6. Fetch secrets from GCP metadata service
7. Create .env file with credentials
8. Create systemd service file
9. systemctl enable specterbot
10. systemctl start specterbot
```

**Metadata Service Integration**:
```bash
TELEGRAM_BOT_TOKEN=$(curl -s \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/telegram-bot-token" \
  -H "Metadata-Flavor: Google")
```

**Instance Setup**:
1. Create VM instance in GCP Console
2. Set metadata attributes: `telegram-bot-token`, `telegram-chat-id`
3. Paste startup-script.sh as startup script
4. Boot VM
5. Bot auto-starts via systemd

**Service Management**:
```bash
# View logs
sudo journalctl -u specterbot -f

# Check status
sudo systemctl status specterbot

# Restart
sudo systemctl restart specterbot

# Stop
sudo systemctl stop specterbot
```

---

## State Management

### call_state.json Schema

**Location**: Same directory as bot.py

**Format**:
```json
{
  "call_number": 10,
  "topics": [
    "PR review improvements",
    "New CI/CD pipeline",
    "Community feedback"
  ]
}
```

**Default** (if file doesn't exist):
```json
{
  "call_number": 9,
  "topics": []
}
```

### State Operations

**Load State**:
```python
def load_call_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"call_number": 9, "topics": []}
```
- Called before every use of state
- Returns fresh dict from file

**Save State**:
```python
def save_call_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
```
- Called after every state modification
- Writes immediately (synchronous)
- Pretty-printed with 2-space indent

**Get Call Number**:
```python
def get_next_call_number() -> int:
    state = load_call_state()
    return state.get("call_number", 9)
```
- Always returns fresh value from file
- Fallback to 9 if missing

**Increment Call Number**:
```python
def increment_call_number() -> int:
    state = load_call_state()
    state["call_number"] = state.get("call_number", 9) + 1
    state["topics"] = []  # Reset topics
    save_call_state(state)
    return state["call_number"]
```
- Called after video is posted
- Increments counter
- ALSO resets topics list for next call
- Transactional: load → modify → save

### State Persistence Strategy

**Why JSON not database?**
- Simple deployment (no database setup)
- Easy to inspect/edit manually
- Sufficient for small state
- GCP Compute Engine disk is persistent

**Concurrency Model**:
- Single bot instance (no distributed locking needed)
- Each operation: load → modify → save
- File I/O is atomic enough for this use case
- Race conditions unlikely in practice

**Data Loss Prevention**:
- GCP Compute Engine persistent disk survives reboots
- Startup script clones fresh repo but doesn't delete call_state.json (persists from previous runs)
- Manual backups: check call_state.json into git if desired

### Memory State

**last_posted_video_id**:
```python
last_posted_video_id: Optional[str] = None
```
- Global variable in bot.py
- Tracks most recently posted video ID
- Prevents duplicate posting
- Lost on restart (acceptable - can rely on YouTube upload date uniqueness)

---

## Bot Commands Reference

### /start
**Handler**: `start_command()` (lines 151-166)
**Response**: Welcome message with command list
**State Modified**: None
**Example**:
```
Hello! I'm the Specter DIY Builder Bot.
I automatically send reminders for the weekly call and post links to the recordings.
Next call: #10
Commands:
/help - Show help
/status - Show bot status
[... etc]
```

### /help
**Handler**: `help_command()` (lines 169-191)
**Response**: Detailed help about bot capabilities
**State Modified**: None
**Format**: Markdown with sections
**Content**: Core purpose, automated tasks, available commands

### /status
**Handler**: `status_command()` (lines 194-208)
**Response**: Current bot status and configuration
**State Modified**: None
**Shows**:
- Status: Running
- Current time (Europe/Berlin timezone)
- Next call number
- Schedule frequency
- Reminder times

### /nextcall
**Handler**: `nextcall_info_command()` (lines 211-242)
**Response**: Next call details with countdown
**State Modified**: None
**Shows**:
- Call number with emoji
- Date (full format: "Thursday, 26 December 2024")
- Time in MEZ (Central European Time)
- Countdown (days, hours, minutes)
- Topics list (or "No topics set yet")
- Links: Jitsi, Calendar

### /topic <topic_text>
**Handler**: `topic_command()` (lines 245-260)
**Arguments**: Any text after /topic
**State Modified**: Appends to topics list, saves state
**Validation**: Requires at least 1 argument
**Response**: Confirmation message with topic text
**Example**:
```
User: /topic New deployment pipeline
Bot: ✅ Topic added: "New deployment pipeline"
```

### /latestvideo
**Handler**: `latest_video_command()` (lines 263-282)
**Response**: Most recent video with AI summary
**State Modified**: None (doesn't increment call number)
**Process**:
1. User sees "🔎 Searching for latest video..."
2. Bot fetches latest from YouTube
3. Bot generates AI summary
4. Posts video link with title and summary
**Error**: "❌ Could not find any video in the playlist"

### /chatid
**Handler**: `chatid_command()` (lines 285-288)
**Response**: Chat ID of current conversation
**State Modified**: None
**Purpose**: Get chat ID for initial .env setup
**Response Format**: "🔑 Your Chat ID is: `<id>`" (in monospace)

### /callnumber [number]
**Handler**: `callnumber_command()` (lines 291-308)
**Arguments**: Optional number to set (positive integer)
**Response**:
- If no arg: "🔢 Current call number is #N"
- If valid number: "✅ Call number updated to #N"
- If invalid: "Invalid number. Please use a positive integer."
**State Modified**: Updates call_number in state if number provided
**Validation**: Must be positive integer
**Use Case**: Manual correction if call numbering gets out of sync

### /postvideo
**Handler**: `post_video_command()` (lines 311-314)
**Response**: "⏳ Posting latest video..."
**State Modified**: Increments call number, resets topics (if new video found)
**Trigger**: Manually triggers `check_and_post_new_video()`
**Use Case**: Admin command to immediately post latest recording
**Side Effects**:
- Posts video with summary
- Increments call number
- Updates last_posted_video_id

---

## Message Templates

All templates are in `config.py` (lines 83-143). Messages are in **English**.

### Message Formatting

**Parse Mode**: HTML (`ParseMode.HTML`)
- All messages use HTML formatting for proper link rendering
- Links use syntax: `<a href="URL">text</a>` to create clickable text
- Example: `<a href="{calendar_link}">Calendar</a>` renders as clickable "Calendar" text
- HTML special characters must be escaped: `<` → `&lt;`, `>` → `&gt;`

**Link Display**:
- Calendar and Jitsi links show as clickable text (URL hidden)
- Users click on words like "Calendar" or "Jitsi" instead of seeing full URLs
- `disable_web_page_preview=True` prevents large link previews in chat

### Template Variables

These placeholders are replaced dynamically:
- `{call_number}` → Current call number (e.g., "#9")
- `{date}` → Date in DD.MM format (e.g., "19.12")
- `{hour}` → Hour (17 for 17:00)
- `{minute}` → Minute (00)
- `{topics}` → Formatted topic list with bullets
- `{calendar_link}` → Google Calendar link
- `{jitsi_link}` → Jitsi meeting link
- `{youtube_link}` → YouTube channel livestream link
- `{title}` → Video title
- `{summary}` → AI-generated summary
- `{url}` → Video URL

### REMINDER_MESSAGE_3_DAYS

**Sent**: 72 hours (3 days) before Thursday 17:00

**Content**:
```
🗓️ Specter DIY Builder Call #{call_number} in 3 Days! 🛠️

Our weekly Specter DIY Builder Call takes place on {date} at {hour:02d}:{minute:02d} CET.

We discuss PRs, new ideas, and everything about Specter DIY development.

📝 Planned Topics:
{topics}

Note: The call will be livestreamed on YouTube. 🎥

Have topic suggestions? Use /topic <your topic> or forward a message to the bot!

📅 <a href="{calendar_link}">Calendar</a>
🔗 <a href="{jitsi_link}">Jitsi</a>
```

**Tone**: Friendly, informative, invites topic suggestions
**Links**: "Calendar" and "Jitsi" are clickable HTML links

### REMINDER_MESSAGE_1_DAY

**Sent**: 24 hours (1 day) before Thursday 17:00

**Content**:
```
📢 Tomorrow: Specter DIY Builder Call #{call_number}!

Tomorrow at {hour:02d}:{minute:02d} CET (as every week).

Topics include:
{topics}

We look forward to your participation!

📅 <a href="{calendar_link}">Calendar</a>
🔗 <a href="{jitsi_link}">Jitsi</a>
```

**Tone**: Reminder with topics, less promotional
**Links**: "Calendar" and "Jitsi" are clickable HTML links

**Topics Format**:
- If topics exist: Bullet list "• Topic 1\n• Topic 2\n..."
- If none: "No topics set yet."

### REMINDER_MESSAGE_1_HOUR

**Sent**: 1 hour before Thursday 17:00

**Content**:
```
🚀 Specter DIY Builder Call #{call_number} starts in 1 HOUR!

Today at {hour:02d}:{minute:02d} CET - join us!

📝 Topics:
{topics}

🔗 <a href="{jitsi_link}">Jitsi</a>
📺 <a href="{youtube_link}">YouTube Livestream</a>
```

**Tone**: Urgent, last-minute reminder with action links
**Links**: "Jitsi" and "YouTube Livestream" are clickable HTML links

### POST_CALL_MESSAGE_TEMPLATE

**Sent**: Day after call at 12:00 noon (if new video found)

**Content**:
```
✅ *Aufzeichnung verfügbar: Specter DIY Builder Call #{call_number}*

Call verpasst oder nochmal ansehen? Kein Problem!

🎬 *{title}*

📝 *Zusammenfassung (automatisch generiert):*
{summary}

🔗 *Hier ansehen:* {url}

Bis nächste Woche! 👋
```

**Tone**: Celebratory, helpful, includes summary

**Summary Origin**:
- Generated by Gemini AI from video description
- Or truncated description if API unavailable
- Format: Bullet points in German

### TOPIC_ANNOUNCEMENT_MESSAGE

**Note**: Defined in config.py but not actively used in current code (legacy)

**Content**:
```
📣 *Themen für den Call #{call_number} am Donnerstag*

Wir werden über Folgendes sprechen:
{topics}

Habt ihr weitere Vorschläge? Lasst es uns wissen! 👇
```

---

## Configuration and Environment

### .env File

**Location**: Root directory (same as bot.py)

**Example** (.env.example):
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
YOUTUBE_PLAYLIST_ID=PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm
```

**Optional**:
```
GEMINI_API_KEY=your_gemini_api_key  # Optional - falls back to truncated summaries
YOUTUBE_CHANNEL_ID=UCs_tO31-N62qAD_S7s_H-8w  # Usually doesn't need changing
```

### Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | None | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes* | None | Target chat ID (use /chatid to find) |
| `GEMINI_API_KEY` | No | None | Google Gemini AI API key |
| `YOUTUBE_PLAYLIST_ID` | No | PLn2... | YouTube playlist ID |
| `YOUTUBE_CHANNEL_ID` | No | UCs_tO... | YouTube channel ID |

*Required for full functionality (scheduler won't start without it)

### Config Class

Located in `config.py` lines 43-157.

**Constants**:
```python
class Config:
    CALL_DAY = "thursday"        # Day of week
    CALL_HOUR = 17              # Hour (24h format)
    CALL_MINUTE = 0             # Minute
    TIMEZONE = "Europe/Berlin"  # Timezone for scheduling

    REMINDERS = [72, 24, 1]     # Reminder times in hours

    CALENDAR_LINK = "https://calendar.app.google/7cWw2rLLFhrBMhtF8"
    JITSI_LINK = "https://meet.jit.si/SpecterBuilderCall"
```

**Methods**:
```python
@classmethod
def validate(cls, require_chat_id: bool = True):
    # Check TELEGRAM_BOT_TOKEN always required
    # Check TELEGRAM_CHAT_ID if require_chat_id=True
    # Raises ValueError if validation fails

@classmethod
def is_fully_configured(cls) -> bool:
    # Returns True if both bot token AND chat ID are set
    # Used to determine if scheduler should start
```

### Customization Examples

**Change Call Time**:
```python
# In config.py
CALL_HOUR = 19  # 7 PM instead of 5 PM
CALL_MINUTE = 30  # Half past the hour
```

**Change Reminders**:
```python
# In config.py
REMINDERS = [48, 12, 2]  # 2 days, 12 hours, 2 hours before
```

**Change Timezone**:
```python
# In config.py
TIMEZONE = "America/New_York"  # EST instead of CET
```

**Change Jitsi/Calendar Links**:
```python
# In config.py
JITSI_LINK = "https://meet.jit.si/YourMeetingName"
CALENDAR_LINK = "https://your.calendar.link"
```

---

## Google Cloud Deployment

### Prerequisites

1. GCP account with billing enabled
2. Telegram bot token from @BotFather
3. Telegram chat ID (from /chatid command)
4. Gemini API key (optional)

### Step-by-Step Deployment

1. **Create Compute Engine Instance**
   - Go to GCP Console → Compute Engine → VM Instances
   - Click "Create Instance"
   - Configuration:
     - Name: `specter-bot` (or preferred name)
     - Region: `europe-west1` (closest to CET)
     - Machine type: `e2-micro` (free tier)
     - Boot disk: 20GB (default)
     - OS: Debian 11 or Ubuntu 22.04

2. **Set Metadata**
   - Still in create instance dialog, scroll to "Management, security, disks, networking, sole tenancy"
   - Click "Management" tab
   - Under "Metadata", add two custom metadata entries:
     - Key: `telegram-bot-token`, Value: Your token
     - Key: `telegram-chat-id`, Value: Your chat ID

3. **Set Startup Script**
   - In create instance dialog, under "Management" tab, find "Startup script"
   - Paste entire contents of `startup-script.sh`

4. **Create Instance**
   - Click "Create"
   - Wait for instance to boot and startup script to run (1-2 minutes)

5. **Verify Deployment**
   - Click on instance name to open details
   - Click "SSH" to open terminal
   - Run: `sudo systemctl status specterbot`
   - Expected output: `Active (running)`
   - View logs: `sudo journalctl -u specterbot -f`

### Startup Script Breakdown

**Lines 4-8**: Dependencies
```bash
apt-get update
apt-get install -y python3 python3-pip python3-venv git
```
Installs Python and Git.

**Lines 10-11**: Create bot user
```bash
useradd -m -s /bin/bash botuser || true
```
Non-root user for security. `|| true` prevents error if user exists.

**Lines 13-21**: Clone/update repo
```bash
cd /home/botuser
if [ -d "Specter-DIY-Builder-Bot" ]; then
    cd Specter-DIY-Builder-Bot && git pull
else
    git clone https://github.com/Schnuartz/Specter-DIY-Builder-Bot.git
    cd Specter-DIY-Builder-Bot
fi
```
Fresh clone or update existing repo.

**Lines 23-25**: Python setup
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```
Isolated Python environment with dependencies.

**Lines 27-35**: .env generation from metadata
```bash
TELEGRAM_BOT_TOKEN=$(curl -s \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/telegram-bot-token" \
  -H "Metadata-Flavor: Google")
TELEGRAM_CHAT_ID=$(curl -s \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/telegram-chat-id" \
  -H "Metadata-Flavor: Google")

cat > .env << EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
YOUTUBE_PLAYLIST_ID=PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm
EOF
```
Fetches secrets from GCP metadata service and creates .env file.

**Lines 37-38**: Ownership
```bash
chown -R botuser:botuser /home/botuser/Specter-DIY-Builder-Bot
```
Non-root user owns the files.

**Lines 40-58**: Systemd service
```bash
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
```
Creates systemd service that:
- Runs as `botuser`
- Auto-restarts on crash (Restart=always, RestartSec=10)
- Logs to systemd journal
- Auto-starts on VM boot

**Lines 60-63**: Start service
```bash
systemctl daemon-reload
systemctl enable specterbot
systemctl start specterbot
```
Enable autostart and start immediately.

### Ongoing Management

**Check Status**:
```bash
gcloud compute ssh [instance-name]
sudo systemctl status specterbot
```

**View Logs**:
```bash
sudo journalctl -u specterbot -f  # Follow logs
sudo journalctl -u specterbot -n 100  # Last 100 lines
```

**Restart Bot**:
```bash
sudo systemctl restart specterbot
```

**Stop Bot**:
```bash
sudo systemctl stop specterbot
sudo systemctl disable specterbot  # Disable autostart
```

**Update Code**:
```bash
cd /home/botuser/Specter-DIY-Builder-Bot
sudo -u botuser git pull
sudo systemctl restart specterbot
```

### Troubleshooting GCP Deployment

**Service won't start**:
- Check logs: `sudo journalctl -u specterbot -n 50`
- Verify .env file: `cat .env` (should have token and chat ID)
- Verify Python venv: `ls -la venv/bin/python`

**Bot doesn't send messages**:
- Verify chat ID is correct: `python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('TELEGRAM_CHAT_ID'))"`
- Check if bot has permissions in the group
- Verify token: Try `/start` command in group

**yt-dlp errors in logs**:
- YouTube API may have changed
- Update yt-dlp: `venv/bin/pip install --upgrade yt-dlp`
- Restart: `sudo systemctl restart specterbot`

---

## Error Handling

### Graceful Degradation Strategy

The bot is designed to fail gracefully:

1. **Missing Gemini API Key**:
   - AI summaries won't work
   - Falls back to truncated description (first 500 chars)
   - Bot still posts video
   - Logs warning but doesn't crash

2. **YouTube Extraction Fails**:
   - Returns None
   - check_and_post_new_video() logs warning and returns
   - Doesn't crash scheduler
   - Next attempt on next scheduled check

3. **Telegram Message Send Fails**:
   - Exception caught in try/except
   - Logged as error
   - Execution continues
   - Next reminder still sent as scheduled

4. **Invalid Configuration**:
   - Bot startup checks Config.validate()
   - If missing token: Raises ValueError, bot exits
   - If missing chat ID: Logs "SETUP MODE", bot runs without scheduler
   - User can add /chatid and restart

### Try/Except Blocks

**send_reminder()**:
```python
try:
    await bot.send_message(...)
    logger.info("Reminder sent successfully")
except Exception as e:
    logger.error(f"Failed to send reminder: {e}")
```

**check_and_post_new_video()**:
```python
try:
    await bot.send_message(...)
    last_posted_video_id = video.video_id
except Exception as e:
    logger.error(f"Failed to post video: {e}")
```

**summarize_with_ai()**:
```python
try:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return response.text.strip()
except Exception as e:
    logger.error(f"Error calling Gemini API: {e}")
    return text[:500].strip() + "..."  # Fallback
```

**get_latest_video_from_playlist()**:
```python
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(playlist_url, download=False)
        # ... extraction logic
        return VideoInfo(...)
except Exception as e:
    logger.error(f"Error fetching playlist: {e}")
    return None
```

### Logging Levels

**INFO**: Normal operation
- "Reminder sent successfully..."
- "Posted new video..."
- "Scheduled job: ... at ..."
- "Bot is running..."

**WARNING**: Potential issues
- "SETUP MODE: Chat ID not set"
- "GEMINI_API_KEY is not configured"
- "Could not fetch latest video"
- "Video ... already posted"

**ERROR**: Failures that don't crash
- "Failed to send reminder: ..."
- "Failed to post video: ..."
- "Error calling Gemini API: ..."
- "Error fetching playlist: ..."
- "Configuration error: ..."

### Common Error Messages

**"No entries found in playlist"**:
- Playlist ID wrong or empty
- YouTube blocked yt-dlp
- Network issue

**"Error calling Gemini API: ..."**:
- API key invalid
- Quota exceeded
- Network issue
- Check logs for specifics

**"Failed to send reminder: ..."**:
- Chat ID invalid
- Bot not admin in group
- Bot blocked by Telegram
- Network issue

---

## Testing

### Local Testing

**Prerequisites**:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with test token and chat ID
```

**Run Bot**:
```bash
python bot.py
```

**Send Test Commands**:
- Open Telegram group/chat where bot is member
- Send `/help` to verify it's working
- Send `/status` to check scheduling
- Send `/topic "test topic"` to test state management

### Testing youtube_utils.py Standalone

```bash
python youtube_utils.py
```

This script:
- Fetches latest video from playlist
- Prints video info
- Generates AI summary (if GEMINI_API_KEY configured)
- Useful for testing YouTube extraction and AI independently

**Output** (example):
```
Fetching latest video from playlist PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm...

Title: Specter DIY Builder Call #9
URL: https://www.youtube.com/watch?v=...
Upload Date: 20241219

Summary:
• Neue Security-Features diskutiert
• Performance-Optimierungen implementiert
• Deployment-Prozess verbessert
```

### Testing Scheduler

1. Modify REMINDERS in config.py to test faster:
   ```python
   REMINDERS = [0.05, 0.03, 0.01]  # 3 min, 1.8 min, 0.6 min
   ```

2. Run bot: `python bot.py`

3. Check logs for scheduled jobs with correct timing

4. Watch for reminder messages in your test group

5. Restore REMINDERS after testing

### Testing State Management

```python
# Test in Python REPL
from config import load_call_state, save_call_state, increment_call_number

# Load current
state = load_call_state()
print(state)

# Add topic
state["topics"].append("test topic")
save_call_state(state)

# Increment
new_num = increment_call_number()
print(f"New number: {new_num}")

# Verify reset
state = load_call_state()
print(f"Topics reset: {state['topics']}")
```

---

## Troubleshooting

### Links Not Clickable in Messages

**Symptoms**: Calendar/Jitsi links show as plain text or full URLs instead of clickable text

**Checklist**:
1. ✅ Is parse_mode set to HTML? Check bot.py line 163 and 327
2. ✅ Are links using correct syntax? Should be `<a href="URL">text</a>`
3. ✅ Are HTML special characters escaped? Use `&lt;` for `<` and `&gt;` for `>`
4. ✅ Is disable_web_page_preview set? Should be `True` to hide URL previews

**Solutions**:
- Verify parse_mode: `parse_mode=ParseMode.HTML` in all message sends
- Check template syntax: Links must use `<a href="{calendar_link}">Calendar</a>` format
- Don't use MARKDOWN or MARKDOWN_V2 - they don't support HTML links properly
- HTML mode is simpler and more reliable for text hyperlinks

### Bot Commands Not Responding

**Symptoms**: User sends command, bot doesn't reply

**Checklist**:
1. ✅ Is bot running? Check logs: `python bot.py` or `systemctl status specterbot`
2. ✅ Is bot member of chat? Add bot and check
3. ✅ Is token correct? Try `/start`
4. ✅ Is chat ID correct? Send `/chatid` to get it, compare with .env
5. ✅ Internet connection? Restart bot
6. ✅ Check logs for errors: Look for exception messages

**Solutions**:
- Verify .env: `cat .env`
- Restart: `python bot.py` (locally) or `systemctl restart specterbot` (GCP)
- Verify bot admin: Add bot to group, check "Administrators" section

### Reminders Not Sending

**Symptoms**: Expected reminder not posted to group

**Checklist**:
1. ✅ Is scheduler running? Look for "Scheduled job" messages in logs
2. ✅ Is next Thursday date correct? Send `/status` or `/nextcall`
3. ✅ Is chat ID correct? Verify with `/chatid`
4. ✅ Is bot online? Check with `/status` command

**Solutions**:
- Verify scheduler started: `grep "Scheduled job" bot.log`
- Check timezone: Should be "Europe/Berlin"
- Manually trigger: Send `/postvideo` to test message sending
- Check call_state.json: `cat call_state.json`

### YouTube Video Not Found

**Symptoms**: "/latestvideo" returns "Could not find any video"

**Checklist**:
1. ✅ Is playlist ID correct? Check YOUTUBE_PLAYLIST_ID in config.py
2. ✅ Does playlist have videos? Visit link in browser
3. ✅ Is yt-dlp installed? `python -c "import yt_dlp"`
4. ✅ Is network working? Try `ping youtube.com`

**Solutions**:
- Test youtube_utils.py: `python youtube_utils.py`
- Update yt-dlp: `pip install --upgrade yt-dlp`
- Try different playlist (test URL): `python youtube_utils.py`
- Check logs for yt-dlp error messages

### AI Summary Not Working

**Symptoms**: Video summary is just truncated description

**Checklist**:
1. ✅ Is GEMINI_API_KEY set? Check .env
2. ✅ Is API key valid? Test in AI Studio
3. ✅ Has API quota been exceeded? Check GCP console
4. ✅ Is internet working? Check Telegram messages send

**Solutions**:
- This is graceful degradation - bot still works!
- Get API key: https://aistudio.google.com/app/apikey
- Update .env with key
- Restart bot
- Try `/latestvideo` again

### Bot Crashes/High CPU on GCP

**Symptoms**: Bot service stops, or CPU usage very high

**Checklist**:
1. ✅ Check logs: `journalctl -u specterbot -n 50`
2. ✅ Is there a Python exception?
3. ✅ Is disk full? `df -h`
4. ✅ Is memory exhausted? `free -h`

**Solutions**:
- Increase machine type: e2-small or e2-medium
- Clear logs: `journalctl --vacuum=1G`
- Restart service: `systemctl restart specterbot`
- Check for infinite loops in recent code changes

### State File Corruption

**Symptoms**: Bot crashes with JSON parse error

**Solution**:
```bash
# Backup corrupted file
cp call_state.json call_state.json.bak

# Create fresh state
echo '{"call_number": 9, "topics": []}' > call_state.json

# Restart bot
systemctl restart specterbot
```

### "SETUP MODE" Message

**Symptoms**: Bot runs but doesn't schedule reminders

**Cause**: TELEGRAM_CHAT_ID not set in .env

**Solution**:
1. Send `/chatid` in the Telegram group
2. Copy the displayed ID
3. Add to .env: `TELEGRAM_CHAT_ID=<copied_id>`
4. Restart bot

---

## Additional Resources

### Code References
- Bot main logic: `bot.py`
- Configuration: `config.py`
- YouTube/AI integration: `youtube_utils.py`
- Deployment: `startup-script.sh`

### External Documentation
- python-telegram-bot: https://python-telegram-bot.readthedocs.io/
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- APScheduler: https://apscheduler.readthedocs.io/
- Google Gemini API: https://ai.google.dev/docs

### Community Links
- Specter DIY: https://github.com/Schnuartz/Specter-DIY
- Telegram Group: https://t.me/+93YQ5guL95syMmYy
- YouTube: https://www.youtube.com/@UCs_tO31-N62qAD_S7s_H-8w
