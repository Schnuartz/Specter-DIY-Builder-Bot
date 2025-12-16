"""Configuration management for the Specter DIY Builder Bot."""

import os
from dotenv import load_dotenv

load_dotenv()


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

    # Messages
    REMINDER_MESSAGE_3_DAYS = """
🔔 *Specter DIY Builder Call in 3 Tagen!*

📅 Donnerstag um 17:00 Uhr (CET)
📺 Live auf YouTube

Markiert euch den Termin! Wir freuen uns auf euch.

🔗 YouTube Kanal: https://www.youtube.com/@AnchorWatch
"""

    REMINDER_MESSAGE_1_DAY = """
🔔 *Specter DIY Builder Call MORGEN!*

📅 Donnerstag um 17:00 Uhr (CET)
📺 Live auf YouTube

Nicht vergessen - morgen ist es soweit!

🔗 YouTube Kanal: https://www.youtube.com/@AnchorWatch
"""

    REMINDER_MESSAGE_1_HOUR = """
🚀 *Specter DIY Builder Call in 1 STUNDE!*

📅 Heute um 17:00 Uhr (CET)
📺 Live auf YouTube

Macht euch bereit - gleich geht's los!

🔗 YouTube Kanal: https://www.youtube.com/@AnchorWatch
"""

    POST_CALL_MESSAGE_TEMPLATE = """
📺 *Specter DIY Builder Call - Aufzeichnung verfügbar!*

Ihr habt den Call verpasst oder wollt ihn nochmal anschauen? Kein Problem!

🎬 *{title}*

📝 *Zusammenfassung:*
{summary}

🔗 *Zum Video:* {url}

Bis zum nächsten Mal! 👋
"""

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not cls.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID is required")
        return True
