"""Configuration management for the Specter DIY Builder Bot."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Import after Config is needed, so we'll handle circular import carefully
_youtube_utils = None

# Path for storing call state (number, topics, etc.)
STATE_FILE = Path(__file__).parent / "call_state.json"


def load_call_state() -> dict:
    """Load the current call state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"call_number": 9, "topics": []}  # Default starting number


def save_call_state(state: dict) -> None:
    """Save the call state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_next_call_number() -> int:
    """
    Get the next call number from the latest video in the playlist.
    Extracts the call number from the video title (e.g., "Call #10").
    The next call number = latest call number + 1.
    """
    global _youtube_utils

    # Lazy import to avoid circular dependency
    if _youtube_utils is None:
        from youtube_utils import get_latest_call_number
        _youtube_utils = get_latest_call_number

    # Get the call number from the latest playlist video
    playlist_id = os.getenv("YOUTUBE_PLAYLIST_ID", "PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm")
    next_call = _youtube_utils(playlist_id)

    if next_call > 0:
        return next_call

    # Fallback to state file if playlist fetch fails
    state = load_call_state()
    return state.get("call_number", 1)


def increment_call_number() -> int:
    """Increment the call number after a call."""
    state = load_call_state()
    state["call_number"] = state.get("call_number", 9) + 1
    state["topics"] = []  # Reset topics for next call
    save_call_state(state)
    return state["call_number"]


class Config:
    """Bot configuration."""

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # YouTube
    YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCs_tO31-N62qAD_S7s_H-8w")
    YOUTUBE_PLAYLIST_ID = os.getenv(
        "YOUTUBE_PLAYLIST_ID",
        "PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm"
    )
    YOUTUBE_PLAYLIST_URL = f"https://www.youtube.com/playlist?list={YOUTUBE_PLAYLIST_ID}"

    # Call Links
    CALENDAR_LINK = "https://calendar.app.google/7cWw2rLLFhrBMhtF8"
    JITSI_LINK = "https://meet.jit.si/SpecterBuilderCall"

    # Schedule (Thursday 17:00 CET)
    CALL_DAY = "thursday"
    CALL_HOUR = 17
    CALL_MINUTE = 0
    TIMEZONE = "Europe/Berlin"  # CET/CEST

    # Reminder times (in hours before the call)
    REMINDERS = [
        72,  # 3 days before
        24,  # 1 day before
        1,   # 1 hour before
    ]

    # Message Templates (English)
    # {call_number} - the call number (e.g., #9)
    # {date} - the date (e.g., 19.12)
    # {topics} - optional topics section

    REMINDER_MESSAGE_3_DAYS = """
🗓️ *Specter DIY Builder Call #{call_number} in 3 Tagen!* 🛠️

Am Donnerstag, den {date} um {hour:02d}:{minute:02d} Uhr MEZ findet unser wöchentlicher Specter DIY Builder Call statt.

Wir diskutieren PRs, neue Ideen und alles rund um die Entwicklung von Specter DIY.

Zur Info: Der Call wird live auf YouTube gestreamt. 🎥

Hast du Themenvorschläge? Antworte auf diese Nachricht! 💡

📅 Kalender: {calendar_link}
🔗 Jitsi: {jitsi_link}
"""

    REMINDER_MESSAGE_1_DAY = """
📢 *Morgen: Specter DIY Builder Call #{call_number}!*

Morgen, am {date} um {hour:02d}:{minute:02d} Uhr MEZ (wie jede Woche).

Themen sind unter anderem:
{topics}

Wir freuen uns auf eure Teilnahme!

📅 Kalender: {calendar_link}
🔗 Jitsi: {jitsi_link}
"""

    REMINDER_MESSAGE_1_HOUR = """
🚀 *Specter DIY Builder Call #{call_number} startet in 1 STUNDE!*

Heute um {hour:02d}:{minute:02d} Uhr MEZ - sei dabei!

🔗 Jitsi: {jitsi_link}
📺 YouTube Livestream: {youtube_link}
"""

    POST_CALL_MESSAGE_TEMPLATE = """
✅ *Recording Available: Specter DIY Builder Call \\#{call_number}*

Missed the call or want to watch again\\? No problem\\!

🎬 *{title}*

📝 *Summary \\(AI generated\\):*
{summary}

🔗 *Watch here:* {url}

See you next week\\! 👋
"""

    TOPIC_ANNOUNCEMENT_MESSAGE = """
📣 *Themen für den Call \\#{call_number} am Donnerstag*

Wir werden über Folgendes sprechen:
{topics}

Habt ihr weitere Vorschläge\\? Lasst es uns wissen\\! 👇
"""

    @classmethod
    def validate(cls, require_chat_id: bool = True):
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if require_chat_id and not cls.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID is required")
        return True

    @classmethod
    def is_fully_configured(cls) -> bool:
        """Check if all required config is present."""
        return bool(cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_CHAT_ID)
