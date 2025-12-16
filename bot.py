"""
Specter DIY Builder Bot

A Telegram bot that:
1. Sends reminders for the weekly Specter DIY Builder Call (Thursday 17:00 CET)
2. Posts links to the YouTube recording after the call with a summary
3. Tracks call numbers automatically
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config import Config, get_next_call_number, increment_call_number, load_call_state, save_call_state
from youtube_utils import get_latest_video_from_playlist

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Store last posted video ID to avoid duplicates
last_posted_video_id: Optional[str] = None


def get_next_thursday() -> datetime:
    """Get the next Thursday at 17:00 CET."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)

    days_until_thursday = (3 - now.weekday()) % 7
    if days_until_thursday == 0 and now.hour >= 17:
        days_until_thursday = 7

    next_call = now.replace(hour=17, minute=0, second=0, microsecond=0)
    next_call += timedelta(days=days_until_thursday)
    return next_call


def format_message(template: str, call_date: Optional[datetime] = None) -> str:
    """Format a message template with call number, date, and links."""
    call_number = get_next_call_number()

    if call_date is None:
        call_date = get_next_thursday()

    return template.format(
        call_number=call_number,
        date=call_date.strftime("%d.%m"),
        calendar_link=Config.CALENDAR_LINK,
        jitsi_link=Config.JITSI_LINK,
    )


async def send_reminder(bot: Bot, message: str) -> None:
    """Send a reminder message to the configured chat."""
    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        logger.info("Reminder sent successfully")
    except Exception as e:
        logger.error(f"Failed to send reminder: {e}")


async def send_3_day_reminder(bot: Bot) -> None:
    """Send the 3-day reminder."""
    logger.info("Sending 3-day reminder...")
    message = format_message(Config.REMINDER_MESSAGE_3_DAYS)
    await send_reminder(bot, message)


async def send_1_day_reminder(bot: Bot) -> None:
    """Send the 1-day reminder."""
    logger.info("Sending 1-day reminder...")
    message = format_message(Config.REMINDER_MESSAGE_1_DAY)
    await send_reminder(bot, message)


async def send_1_hour_reminder(bot: Bot) -> None:
    """Send the 1-hour reminder."""
    logger.info("Sending 1-hour reminder...")
    message = format_message(Config.REMINDER_MESSAGE_1_HOUR)
    await send_reminder(bot, message)


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

    # Get current call number before incrementing
    call_number = get_next_call_number()

    # Post the video
    message = Config.POST_CALL_MESSAGE_TEMPLATE.format(
        call_number=call_number,
        title=video.title,
        summary=video.summary,
        url=video.url,
    )

    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False,
        )
        last_posted_video_id = video.video_id
        logger.info(f"Posted new video: {video.title}")

        # Increment call number for next week
        new_number = increment_call_number()
        logger.info(f"Call number incremented to #{new_number}")
    except Exception as e:
        logger.error(f"Failed to post video: {e}")


# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    call_number = get_next_call_number()
    await update.message.reply_text(
        f"Hello! I'm the Specter DIY Builder Bot.\n\n"
        f"I automatically send reminders for the weekly call "
        f"and post links to the recordings.\n\n"
        f"Next call: #{call_number}\n\n"
        f"Commands:\n"
        f"/status - Show bot status\n"
        f"/nextcall - Show next call info\n"
        f"/latestvideo - Show latest video\n"
        f"/callnumber - Show/set call number\n"
        f"/chatid - Show chat ID (for setup)"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    call_number = get_next_call_number()

    await update.message.reply_text(
        f"*Bot Status*\n\n"
        f"Status: Running\n"
        f"Current time: {now.strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Next call: #{call_number}\n"
        f"Schedule: Thursday 17:00 CET\n"
        f"Reminders: 3 days, 1 day, 1 hour before",
        parse_mode=ParseMode.MARKDOWN,
    )


async def next_call_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nextcall command."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    next_call = get_next_thursday()
    call_number = get_next_call_number()

    time_until = next_call - now
    days = time_until.days
    hours = time_until.seconds // 3600
    minutes = (time_until.seconds % 3600) // 60

    await update.message.reply_text(
        f"*Next Specter DIY Builder Call #{call_number}*\n\n"
        f"Date: {next_call.strftime('%A, %d %B %Y')}\n"
        f"Time: 17:00 CET\n\n"
        f"In {days} days, {hours} hours and {minutes} minutes\n\n"
        f"Calendar: {Config.CALENDAR_LINK}\n"
        f"Jitsi: {Config.JITSI_LINK}",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def latest_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latestvideo command."""
    await update.message.reply_text("Searching for latest video...")

    video = get_latest_video_from_playlist(Config.YOUTUBE_PLAYLIST_ID)

    if video:
        # Use current call number - 1 for the latest video (already posted)
        call_number = get_next_call_number() - 1
        if call_number < 1:
            call_number = 1

        message = Config.POST_CALL_MESSAGE_TEMPLATE.format(
            call_number=call_number,
            title=video.title,
            summary=video.summary,
            url=video.url,
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Could not find any video.")


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chatid command - useful for setup."""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    chat_title = update.effective_chat.title or "Private Chat"

    await update.message.reply_text(
        f"*Chat Information*\n\n"
        f"Chat ID: `{chat_id}`\n"
        f"Type: {chat_type}\n"
        f"Name: {chat_title}\n\n"
        f"Add this to your `.env` file:\n"
        f"`TELEGRAM_CHAT_ID={chat_id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def callnumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /callnumber command - show or set call number."""
    call_number = get_next_call_number()

    # Check if a new number was provided
    if context.args and len(context.args) > 0:
        try:
            new_number = int(context.args[0])
            if new_number > 0:
                state = load_call_state()
                state["call_number"] = new_number
                save_call_state(state)
                await update.message.reply_text(
                    f"Call number updated to #{new_number}",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
        except ValueError:
            pass

    await update.message.reply_text(
        f"*Current Call Number: #{call_number}*\n\n"
        f"To change it, use:\n"
        f"`/callnumber <number>`\n\n"
        f"Example: `/callnumber 10`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def post_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /postvideo command - manually trigger video post."""
    await update.message.reply_text("Posting latest video...")
    await check_and_post_new_video(context.bot)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Set up the scheduler for reminders and video checks."""
    scheduler = AsyncIOScheduler(timezone=Config.TIMEZONE)

    # 3 days before (Monday 17:00)
    scheduler.add_job(
        lambda: __import__('asyncio').create_task(send_3_day_reminder(bot)),
        CronTrigger(day_of_week="mon", hour=17, minute=0),
        id="reminder_3_days",
        name="3-day reminder",
    )

    # 1 day before (Wednesday 17:00)
    scheduler.add_job(
        lambda: __import__('asyncio').create_task(send_1_day_reminder(bot)),
        CronTrigger(day_of_week="wed", hour=17, minute=0),
        id="reminder_1_day",
        name="1-day reminder",
    )

    # 1 hour before (Thursday 16:00)
    scheduler.add_job(
        lambda: __import__('asyncio').create_task(send_1_hour_reminder(bot)),
        CronTrigger(day_of_week="thu", hour=16, minute=0),
        id="reminder_1_hour",
        name="1-hour reminder",
    )

    # Check for new videos every Friday at 12:00 (day after the call)
    scheduler.add_job(
        lambda: __import__('asyncio').create_task(check_and_post_new_video(bot)),
        CronTrigger(day_of_week="fri", hour=12, minute=0),
        id="video_check",
        name="Video check",
    )

    # Also check every 6 hours on Friday and Saturday to catch delayed uploads
    scheduler.add_job(
        lambda: __import__('asyncio').create_task(check_and_post_new_video(bot)),
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
        call_number = get_next_call_number()
        logger.info(f"Starting Specter DIY Builder Bot (Next call: #{call_number})...")

    # Create application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("nextcall", next_call_command))
    application.add_handler(CommandHandler("latestvideo", latest_video_command))
    application.add_handler(CommandHandler("chatid", chatid_command))
    application.add_handler(CommandHandler("callnumber", callnumber_command))
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
