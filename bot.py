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
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from config import Config, get_next_call_number, increment_call_number, load_call_state, save_call_state, invalidate_topics_cache
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


def get_calendar_link_for_call(call_date: datetime) -> str:
    """Generate a Google Calendar link for a specific call date.

    Args:
        call_date: The datetime of the call (Thursday 17:00 CET)

    Returns:
        Google Calendar template URL for adding the event
    """
    from urllib.parse import urlencode

    # Format dates for Google Calendar (YYYYMMDDTHHMMSSZ in UTC)
    # Call is 17:00 CET = 16:00 UTC (or 15:00 UTC in summer)
    start_utc = call_date.astimezone(pytz.UTC)
    end_utc = start_utc + timedelta(hours=2)  # 2-hour call

    start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")
    end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")

    # Build Google Calendar template URL
    params = {
        "action": "TEMPLATE",
        "text": "Specter DIY Builder Call",
        "dates": f"{start_str}/{end_str}",
        "details": "Weekly Specter DIY Builder community call. Discuss PRs, new ideas, and development.",
        "location": Config.JITSI_LINK,
    }

    query = urlencode(params)
    return f"https://calendar.google.com/calendar/render?{query}"


def format_message(template: str, call_date: Optional[datetime] = None, topics: list = None, use_ai_topics: bool = True) -> str:
    """Format a message template with call number, date, topics, and links.

    Args:
        template: Message template string
        call_date: Date of the call (defaults to next Thursday)
        topics: List of topic strings
        use_ai_topics: Whether to format topics with AI (default True)
    """
    call_number = get_next_call_number()

    if call_date is None:
        call_date = get_next_thursday()

    # Format topics
    if topics:
        if use_ai_topics:
            # Check cache first
            state = load_call_state()
            cached = state.get("topics_formatted_cache")

            if cached:
                topic_str = cached
            else:
                # Generate with AI and cache
                from youtube_utils import format_topics_with_ai
                topic_str = format_topics_with_ai(topics, call_number)
                state["topics_formatted_cache"] = topic_str
                save_call_state(state)
        else:
            # Simple bullet points
            topic_str = "\n".join(f"• {t}" for t in topics)
    else:
        topic_str = "No topics set yet."

    # Generate dynamic calendar link
    calendar_link = get_calendar_link_for_call(call_date)

    return template.format(
        call_number=call_number,
        date=call_date.strftime("%d.%m"),
        hour=Config.CALL_HOUR,
        minute=Config.CALL_MINUTE,
        topics=topic_str,
        calendar_link=calendar_link,
        jitsi_link=Config.JITSI_LINK,
        youtube_link=f"https://www.youtube.com/@{Config.YOUTUBE_CHANNEL_ID}/live"
    )


async def is_user_admin(bot: Bot, user_id: int) -> bool:
    """Check if a user is an admin in the configured Telegram group.

    Args:
        bot: The Bot instance
        user_id: Telegram user ID to check

    Returns:
        True if user is admin or creator, False otherwise
    """
    try:
        chat_member = await bot.get_chat_member(
            chat_id=Config.TELEGRAM_CHAT_ID,
            user_id=user_id
        )
        return chat_member.status in ["creator", "administrator"]
    except Exception as e:
        logger.error(f"Failed to check admin status for user {user_id}: {e}")
        return False


async def send_reminder(bot: Bot, template: str) -> None:
    """Send a reminder message to the configured chat."""
    state = load_call_state()
    topics = state.get("topics", [])
    message = format_message(template, topics=topics)

    try:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2,
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
        "`/topic <text>` - (Admin) Add a topic for the next call. You can also forward messages to the bot to add them as topics.\n"
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

    # Format topics - use AI summarization if topics exist
    if topics:
        from youtube_utils import format_topics_with_ai
        topic_str = format_topics_with_ai(topics, call_number)
    else:
        topic_str = "No topics set yet."

    calendar_link = get_calendar_link_for_call(next_call)

    await update.message.reply_text(
        f"🗓️ *Next Specter DIY Builder Call #{call_number}*\n\n"
        f"📅 *Date*: {next_call.strftime('%A, %d %B %Y')}\n"
        f"⏰ *Time*: {Config.CALL_HOUR}:{Config.CALL_MINUTE:02d} CET\n\n"
        f"⏳ *Countdown*: {days} days, {hours} hours, {minutes} minutes\n\n"
        f"📝 *Topics*:\n{topic_str}\n\n"
        f"🔗 *Join the Call*:\n"
        f"• [Jitsi]({Config.JITSI_LINK})\n"
        f"• [Calendar]({calendar_link})",
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )


async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /topic command to add a topic (admin only)."""
    # Check if user is admin
    user_id = update.effective_user.id
    if not await is_user_admin(context.bot, user_id):
        await update.message.reply_text(
            "❌ Only group administrators can add topics."
        )
        return

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
    invalidate_topics_cache()

    await update.message.reply_text(f"✅ Topic added: \"{topic}\"")


async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle forwarded messages - add them as topics if sender is admin.

    Admins can forward messages from the group to the bot (in DM or group),
    and the forwarded message text will be added as a topic for the next call.
    """
    message = update.message

    # Only process if message was forwarded
    if not message.forward_date:
        return

    # Check if user is admin
    user_id = update.effective_user.id
    if not await is_user_admin(context.bot, user_id):
        await message.reply_text(
            "❌ Only group administrators can add topics via forwarded messages."
        )
        return

    # Extract text from forwarded message
    topic_text = None

    if message.text:
        topic_text = message.text
    elif message.caption:
        topic_text = message.caption
    else:
        await message.reply_text(
            "❌ Could not extract text from forwarded message. "
            "Please forward messages with text or captions."
        )
        return

    # Limit topic length to avoid spam
    if len(topic_text) > 500:
        topic_text = topic_text[:500] + "..."

    # Add topic to state
    state = load_call_state()
    topics = state.get("topics", [])
    topics.append(topic_text)
    state["topics"] = topics
    save_call_state(state)
    invalidate_topics_cache()

    await message.reply_text(
        f"✅ Forwarded message added as topic:\n\n\"{topic_text[:100]}{'...' if len(topic_text) > 100 else ''}\""
    )
    logger.info(f"Topic added from forwarded message by user {user_id}: {topic_text[:50]}")


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

    # Add message handler for forwarded messages
    application.add_handler(
        MessageHandler(
            filters.FORWARDED & (filters.TEXT | filters.CAPTION),
            handle_forwarded_message
        )
    )

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
