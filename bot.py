"""
Specter DIY Builder Bot

A Telegram bot that:
1. Sends reminders for the weekly Specter DIY Builder Call (Thursday 17:00 CET)
2. Posts links to the YouTube recording after the call with a summary
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config import Config
from youtube_utils import get_latest_video_from_playlist, VideoInfo

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Store last posted video ID to avoid duplicates
last_posted_video_id: Optional[str] = None


async def send_reminder(bot: Bot, message: str) -> None:
    """Send a reminder message to the configured chat."""
    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("Reminder sent successfully")
    except Exception as e:
        logger.error(f"Failed to send reminder: {e}")


async def send_3_day_reminder(bot: Bot) -> None:
    """Send the 3-day reminder."""
    logger.info("Sending 3-day reminder...")
    await send_reminder(bot, Config.REMINDER_MESSAGE_3_DAYS)


async def send_1_day_reminder(bot: Bot) -> None:
    """Send the 1-day reminder."""
    logger.info("Sending 1-day reminder...")
    await send_reminder(bot, Config.REMINDER_MESSAGE_1_DAY)


async def send_1_hour_reminder(bot: Bot) -> None:
    """Send the 1-hour reminder."""
    logger.info("Sending 1-hour reminder...")
    await send_reminder(bot, Config.REMINDER_MESSAGE_1_HOUR)


async def check_and_post_new_video(bot: Bot) -> None:
    """Check for new videos in the playlist and post them."""
    global last_posted_video_id

    logger.info("Checking for new videos in playlist...")

    video = get_latest_video_from_playlist(Config.YOUTUBE_PLAYLIST_ID)

    if not video:
        logger.warning("Could not fetch latest video")
        return

    if video.video_id == last_posted_video_id:
        logger.info(f"Video {video.video_id} already posted, skipping")
        return

    # Post the video
    message = Config.POST_CALL_MESSAGE_TEMPLATE.format(
        title=video.title,
        summary=video.summary,
        url=video.url,
    )

    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )
        last_posted_video_id = video.video_id
        logger.info(f"Posted new video: {video.title}")
    except Exception as e:
        logger.error(f"Failed to post video: {e}")


# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Hallo! Ich bin der Specter DIY Builder Bot.\n\n"
        "Ich sende automatisch Erinnerungen für den wöchentlichen Call "
        "und poste Links zu den Aufzeichnungen.\n\n"
        "Befehle:\n"
        "/status - Zeige Bot-Status\n"
        "/nextcall - Zeige nächsten Call-Termin\n"
        "/latestvideo - Zeige das neueste Video\n"
        "/chatid - Zeige die Chat-ID (für Setup)"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)

    await update.message.reply_text(
        f"🤖 *Bot Status*\n\n"
        f"✅ Bot läuft\n"
        f"🕐 Aktuelle Zeit: {now.strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"📅 Call-Tag: Donnerstag 17:00 CET\n"
        f"🔔 Erinnerungen: 3 Tage, 1 Tag, 1 Stunde vorher",
        parse_mode=ParseMode.MARKDOWN,
    )


async def next_call_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nextcall command."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)

    # Find next Thursday at 17:00
    days_until_thursday = (3 - now.weekday()) % 7
    if days_until_thursday == 0 and now.hour >= 17:
        days_until_thursday = 7

    next_call = now.replace(hour=17, minute=0, second=0, microsecond=0)
    next_call += timedelta(days=days_until_thursday)

    time_until = next_call - now
    days = time_until.days
    hours = time_until.seconds // 3600
    minutes = (time_until.seconds % 3600) // 60

    await update.message.reply_text(
        f"📅 *Nächster Specter DIY Builder Call*\n\n"
        f"🗓 {next_call.strftime('%A, %d. %B %Y')}\n"
        f"🕐 17:00 Uhr (CET)\n\n"
        f"⏳ Noch {days} Tage, {hours} Stunden und {minutes} Minuten",
        parse_mode=ParseMode.MARKDOWN,
    )


async def latest_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latestvideo command."""
    await update.message.reply_text("🔍 Suche nach dem neuesten Video...")

    video = get_latest_video_from_playlist(Config.YOUTUBE_PLAYLIST_ID)

    if video:
        message = Config.POST_CALL_MESSAGE_TEMPLATE.format(
            title=video.title,
            summary=video.summary,
            url=video.url,
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Konnte kein Video finden.")


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chatid command - useful for setup."""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    chat_title = update.effective_chat.title or "Private Chat"

    await update.message.reply_text(
        f"📋 *Chat Information*\n\n"
        f"Chat ID: `{chat_id}`\n"
        f"Typ: {chat_type}\n"
        f"Name: {chat_title}\n\n"
        f"Füge diese ID in deine `.env` Datei ein:\n"
        f"`TELEGRAM_CHAT_ID={chat_id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def post_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /postvideo command - manually trigger video post."""
    # Check if user is admin (optional security)
    await update.message.reply_text("📤 Poste das neueste Video...")
    await check_and_post_new_video(context.bot)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Set up the scheduler for reminders and video checks."""
    scheduler = AsyncIOScheduler(timezone=Config.TIMEZONE)

    # 3 days before (Monday 17:00)
    scheduler.add_job(
        lambda: asyncio.create_task(send_3_day_reminder(bot)),
        CronTrigger(day_of_week="mon", hour=17, minute=0),
        id="reminder_3_days",
        name="3-day reminder",
    )

    # 1 day before (Wednesday 17:00)
    scheduler.add_job(
        lambda: asyncio.create_task(send_1_day_reminder(bot)),
        CronTrigger(day_of_week="wed", hour=17, minute=0),
        id="reminder_1_day",
        name="1-day reminder",
    )

    # 1 hour before (Thursday 16:00)
    scheduler.add_job(
        lambda: asyncio.create_task(send_1_hour_reminder(bot)),
        CronTrigger(day_of_week="thu", hour=16, minute=0),
        id="reminder_1_hour",
        name="1-hour reminder",
    )

    # Check for new videos every Friday at 12:00 (day after the call)
    scheduler.add_job(
        lambda: asyncio.create_task(check_and_post_new_video(bot)),
        CronTrigger(day_of_week="fri", hour=12, minute=0),
        id="video_check",
        name="Video check",
    )

    # Also check every 6 hours on Friday and Saturday to catch delayed uploads
    scheduler.add_job(
        lambda: asyncio.create_task(check_and_post_new_video(bot)),
        CronTrigger(day_of_week="fri,sat", hour="6,18", minute=0),
        id="video_check_extra",
        name="Extra video check",
    )

    return scheduler


def main() -> None:
    """Main function to run the bot."""
    # Validate configuration (allow missing chat_id for setup mode)
    try:
        Config.validate(require_chat_id=False)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file")
        return

    setup_mode = not Config.is_fully_configured()
    if setup_mode:
        logger.warning("=" * 50)
        logger.warning("SETUP MODE: TELEGRAM_CHAT_ID is not configured!")
        logger.warning("Add bot to your group and send /chatid to get the ID")
        logger.warning("Then add it to your .env file and restart the bot")
        logger.warning("=" * 50)
    else:
        logger.info("Starting Specter DIY Builder Bot...")

    # Create application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("nextcall", next_call_command))
    application.add_handler(CommandHandler("latestvideo", latest_video_command))
    application.add_handler(CommandHandler("chatid", chatid_command))
    application.add_handler(CommandHandler("postvideo", post_video_command))

    # Set up scheduler (only if fully configured)
    if not setup_mode:
        scheduler = setup_scheduler(application.bot)
        scheduler.start()
        logger.info("Scheduler started")

        # Log scheduled jobs
        for job in scheduler.get_jobs():
            logger.info(f"Scheduled job: {job.name} - Next run: {job.next_run_time}")

    # Start the bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
