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
from telegram.helpers import escape_markdown

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


def format_message(template: str, call_date: Optional[datetime] = None, topics: list = None) -> str:
    """Format a message template with call number, date, topics, and links."""
    call_number = get_next_call_number()

    if call_date is None:
        call_date = get_next_thursday()

    topic_str = "\n".join(f"• {t}" for t in topics) if topics else "No topics set yet."

    return template.format(
        call_number=call_number,
        date=call_date.strftime("%d.%m"),
        hour=Config.CALL_HOUR,
        minute=Config.CALL_MINUTE,
        topics=topic_str,
        calendar_link=Config.CALENDAR_LINK,
        jitsi_link=Config.JITSI_LINK,
        youtube_link=f"https://www.youtube.com/@{Config.YOUTUBE_CHANNEL_ID}/live"
    )


async def send_reminder(bot: Bot, template: str) -> None:
    """Send a reminder message to the configured chat."""
    state = load_call_state()
    topics = state.get("topics", [])
    message = format_message(template, topics=topics)

    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        logger.info(f"Reminder sent successfully with template: {template[:30]}")
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

    # Get current call number before incrementing
    call_number = get_next_call_number()

    # Post the video
    message = Config.POST_CALL_MESSAGE_TEMPLATE.format(
        call_number=escape_markdown(str(call_number), version=2),
        title=escape_markdown(video.title, version=2),
        summary=escape_markdown(video.summary, version=2),
        url=escape_markdown(video.url, version=2),
    )

    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2,
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
        f"/help - Show this help message\n"
        f"/status - Show bot status\n"
        f"/nextcall - Show next call info\n"
        f"/latestvideo - Show latest video\n"
        f"/callnumber - Show/set call number\n"
        f"/chatid - Show chat ID (for setup)"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "I'm the Specter DIY Builder Bot! Here's what I can do:\n\n"
        "*Core Purpose:*\n"
        "I help the Specter DIY Builder community by automating call reminders and sharing recordings.\n\n"
        "*Automated Tasks:*\n"
        "- Send reminders 3 days, 1 day, and 1 hour before the weekly call (Thursdays 17:00 CET).\n"
        "- After the call, I find the latest video in our YouTube playlist and post it here with a summary.\n"
        "- I automatically keep track of the call number.\n\n"
        "*Available Commands:*\n"
        "`/start` - Welcome message.\n"
        "`/help` - You are here.\n"
        "`/status` - Shows if I'm running correctly and the current time.\n"
        "`/nextcall` - Displays the date, time, and a countdown to the next call.\n"
        "`/latestvideo` - Fetches and displays the most recent video from the playlist.\n"
        "`/postvideo` - (Admin) Manually triggers posting the latest video.\n"
        "`/callnumber [number]` - Shows the current call number. An admin can also set a new one (e.g., `/callnumber 42`).\n"
        "`/chatid` - Shows the ID of this chat (required for initial setup).\n\n"
        "My code is open-source! You can find it on GitHub.",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
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


async def nextcall_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nextcall command to show info."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    next_call = get_next_thursday()
    call_number = get_next_call_number()
    state = load_call_state()
    topics = state.get("topics", [])

    time_until = next_call - now
    days = time_until.days
    hours = time_until.seconds // 3600
    minutes = (time_until.seconds % 3600) // 60

    topic_str = ""
    if topics:
        for i, topic in enumerate(topics):
            topic_str += f"{i+1}. {topic}\n"
    else:
        topic_str = "No topics set yet."

    await update.message.reply_text(
        f"🗓️ *Next Specter DIY Builder Call #{call_number}*\n\n"
        f"📅 *Date*: {next_call.strftime('%A, %d %B %Y')}\n"
        f"⏰ *Time*: {Config.CALL_HOUR}:{Config.CALL_MINUTE:02d} MEZ\n\n"
        f"⏳ *Countdown*: {days} days, {hours} hours, {minutes} minutes\n\n"
        f"📝 *Topics*:\n{topic_str}\n\n"
        f"🔗 *Jitsi*: {Config.JITSI_LINK}\n"
        f"📅 *Calendar*: {Config.CALENDAR_LINK}",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /topic command to add a topic."""
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text(
            "Please provide a topic after the command, e.g., `/topic New feature discussion`"
        )
        return

    state = load_call_state()
    topics = state.get("topics", [])
    topics.append(topic)
    state["topics"] = topics
    save_call_state(state)

    await update.message.reply_text(f"✅ Topic added: \"{topic}\"")


async def latest_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latestvideo command."""
    await update.message.reply_text("🔎 Searching for the latest video...")

    video = get_latest_video_from_playlist(Config.YOUTUBE_PLAYLIST_ID)

    if video:
        call_number = get_next_call_number() - 1
        if call_number < 1:
            call_number = 1

        message = Config.POST_CALL_MESSAGE_TEMPLATE.format(
            call_number=escape_markdown(str(call_number), version=2),
            title=escape_markdown(video.title, version=2),
            summary=escape_markdown(video.summary, version=2),
            url=escape_markdown(video.url, version=2),
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text("❌ Could not find any video in the playlist.")


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chatid command - useful for setup."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🔑 Your Chat ID is: `{chat_id}`")


async def callnumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /callnumber command - show or set call number."""
    call_number = get_next_call_number()

    if context.args and len(context.args) > 0:
        try:
            new_number = int(context.args[0])
            if new_number > 0:
                state = load_call_state()
                state["call_number"] = new_number
                save_call_state(state)
                await update.message.reply_text(f"✅ Call number updated to #{new_number}")
                return
        except ValueError:
            await update.message.reply_text("Invalid number. Please use a positive integer.")
            return

    await update.message.reply_text(f"🔢 Current call number is #{call_number}.")


async def post_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /postvideo command - manually trigger video post."""
    await update.message.reply_text("⏳ Posting latest video...")
    await check_and_post_new_video(context.bot)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Set up the scheduler for reminders and video checks."""
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(Config.TIMEZONE))

    # Schedule reminders
    next_call_time = get_next_thursday()
    for hours_before in Config.REMINDERS:
        reminder_time = next_call_time - timedelta(hours=hours_before)
        job_id = f"reminder_{hours_before}h"

        if hours_before == 72:
            job_func = lambda: send_reminder(bot, Config.REMINDER_MESSAGE_3_DAYS)
        elif hours_before == 24:
            job_func = lambda: send_reminder(bot, Config.REMINDER_MESSAGE_1_DAY)
        elif hours_before == 1:
            job_func = lambda: send_reminder(bot, Config.REMINDER_MESSAGE_1_HOUR)
        else:
            continue

        scheduler.add_job(
            job_func,
            "date",
            run_date=reminder_time,
            id=job_id,
            name=f"{hours_before}h reminder",
        )

    # Schedule video check (day after call)
    video_check_time = next_call_time + timedelta(days=1)
    video_check_time = video_check_time.replace(hour=12, minute=0)
    scheduler.add_job(
        lambda: check_and_post_new_video(bot),
        "date",
        run_date=video_check_time,
        id="video_check",
        name="Video check",
    )

    return scheduler


def main() -> None:
    """Main function to run the bot."""
    try:
        Config.validate(require_chat_id=False)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("nextcall", nextcall_info_command))
    application.add_handler(CommandHandler("topic", topic_command))
    application.add_handler(CommandHandler("latestvideo", latest_video_command))
    application.add_handler(CommandHandler("chatid", chatid_command))
    application.add_handler(CommandHandler("callnumber", callnumber_command))
    application.add_handler(CommandHandler("postvideo", post_video_command))

    if Config.is_fully_configured():
        logger.info("Bot is fully configured. Starting scheduler...")
        scheduler = setup_scheduler(application.bot)
        scheduler.start()
        for job in scheduler.get_jobs():
            logger.info(f"Scheduled job: {job.name} at {job.next_run_time}")
    else:
        logger.warning("SETUP MODE: Chat ID not set. Run /chatid in your group.")

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
