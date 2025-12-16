"""Configuration management for the Specter DIY Builder Bot."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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
    """Get the next call number."""
    state = load_call_state()
    return state.get("call_number", 9)


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

    # YouTube
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
🔔 *Specter DIY Builder Call #{call_number} in 3 days!*

On Thursday {date} at 17:00 CET we have our weekly Specter DIY Builder Call.

Here we discuss PRs and Specter DIY development in any form.

Just to let you know, we are livestreaming this call on YouTube.

Do you have any topics? Reply to this message!

📅 Calendar: {calendar_link}
🔗 Jitsi: {jitsi_link}
"""

    REMINDER_MESSAGE_1_DAY = """
🔔 *Tomorrow: Specter DIY Builder Call #{call_number}*

Tomorrow {date} at 17:00 CET (like every week)

Here we discuss PRs and Specter DIY development in any form.

Just to let you know, we are livestreaming this call on YouTube.

Do you have any topics?

📅 Calendar: {calendar_link}
🔗 Jitsi: {jitsi_link}
"""

    REMINDER_MESSAGE_1_HOUR = """
🚀 *Specter DIY Builder Call #{call_number} starts in 1 HOUR!*

Today at 17:00 CET - join us!

🔗 Jitsi: {jitsi_link}
📺 YouTube Livestream: https://www.youtube.com/@AnchorWatch
"""

    POST_CALL_MESSAGE_TEMPLATE = """
📺 *Specter DIY Builder Call #{call_number} - Recording Available!*

Missed the call or want to watch it again? No problem!

🎬 *{title}*

📝 *Summary:*
{summary}

🔗 *Watch here:* {url}

See you next week! 👋
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
