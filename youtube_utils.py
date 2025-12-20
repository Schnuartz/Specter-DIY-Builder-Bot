"""YouTube utilities for fetching playlist and video data."""

import yt_dlp
import logging
import google.generativeai as genai
from typing import Optional
from dataclasses import dataclass

from config import Config

logger = logging.getLogger(__name__)


def summarize_with_ai(text: str) -> str:
    """Summarize text using Google's Gemini API."""
    if not text:
        return "No content available to summarize."

    if not Config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not configured. Skipping AI summary.")
        return text[:500].strip() + "..." if len(text) > 500 else text

    try:
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = (
            "You are a helpful assistant for a software development community. "
            "Create a VERY SHORT summary of a YouTube video description for a technical community call. "
            "IMPORTANT RULES:\n"
            "- Use EXACTLY 3 bullet points, no more, no less\n"
            "- Each bullet point must be ONE sentence only\n"
            "- DO NOT use bold formatting (**text**) or colons in bullet points\n"
            "- Be extremely concise - focus only on the main technical topics\n"
            "- Use simple format: * Main topic and brief description\n"
            "- Ignore secondary details like links or resources\n\n"
            f"Summarize this:\n\n{text}"
        )
        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return text[:500].strip() + "..." if len(text) > 500 else text


def format_topics_with_ai(topics: list, call_number: int) -> str:
    """Format topics list into engaging English announcement text using Gemini AI.

    Args:
        topics: List of topic strings
        call_number: The call number for context

    Returns:
        Engaging English text about the topics, or fallback bullet points
    """
    if not topics:
        return "No topics set yet."

    if not Config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured. Using simple format.")
        return "\n".join(f"• {t}" for t in topics)

    try:
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        topics_text = "\n".join(f"- {t}" for t in topics)

        prompt = (
            f"You are a community manager for the Specter DIY Builder Community. "
            f"Create a SHORT, ENGAGING English announcement text for Call #{call_number}.\n\n"
            f"IMPORTANT RULES:\n"
            f"- Write 2-3 sentences in English\n"
            f"- Make people excited about the call - be inviting and enthusiastic\n"
            f"- Incorporate the topics NATURALLY into the text (NOT as bullet points!)\n"
            f"- Use a friendly, community-oriented tone (professional but warm)\n"
            f"- No headings or formatting - just flowing text\n"
            f"- Be concise but inviting\n\n"
            f"Topics to be discussed:\n{topics_text}\n\n"
            f"Create the announcement text now:"
        )

        response = model.generate_content(prompt)
        result = response.text.strip()

        # Remove markdown formatting if Gemini adds it
        result = result.replace("**", "").replace("*", "")

        return result

    except Exception as e:
        logger.error(f"Error calling Gemini API for topics: {e}")
        # Fallback to simple bullet points
        return "\n".join(f"• {t}" for t in topics)


@dataclass
class VideoInfo:
    """Information about a YouTube video."""
    video_id: str
    title: str
    url: str
    description: str
    upload_date: str
    duration: int

    @property
    def summary(self) -> str:
        """Generate a summary using AI or fallback to simple extraction."""
        return summarize_with_ai(self.description)


def get_latest_video_from_playlist(playlist_id: str, timeout: int = 10) -> Optional[VideoInfo]:
    """
    Fetch the latest video from a YouTube playlist.

    Args:
        playlist_id: The YouTube playlist ID
        timeout: Timeout in seconds (default 10s)

    Returns:
        VideoInfo object or None if failed
    """
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "playlistend": 1,  # Only get the first (latest) video
        "socket_timeout": timeout,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(playlist_url, download=False)

            if not result or "entries" not in result:
                logger.error("No entries found in playlist")
                return None

            entries = list(result["entries"])
            if not entries:
                logger.error("Playlist is empty")
                return None

            video = entries[0]

            return VideoInfo(
                video_id=video.get("id", ""),
                title=video.get("title", "Unknown Title"),
                url=video.get("webpage_url", ""),
                description=video.get("description", ""),
                upload_date=video.get("upload_date", ""),
                duration=video.get("duration", 0),
            )

    except Exception as e:
        logger.error(f"Error fetching playlist: {e}")
        return None


def get_video_info(video_id: str) -> Optional[VideoInfo]:
    """
    Fetch information about a specific YouTube video.

    Args:
        video_id: The YouTube video ID

    Returns:
        VideoInfo object or None if failed
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video = ydl.extract_info(video_url, download=False)

            if not video:
                return None

            return VideoInfo(
                video_id=video.get("id", ""),
                title=video.get("title", "Unknown Title"),
                url=video.get("webpage_url", video_url),
                description=video.get("description", ""),
                upload_date=video.get("upload_date", ""),
                duration=video.get("duration", 0),
            )

    except Exception as e:
        logger.error(f"Error fetching video info: {e}")
        return None


def get_call_number_from_title(title: str) -> Optional[int]:
    """
    Extract the call number from a video title.
    Looks for pattern like "Call #10" or "#10" in the title.

    Args:
        title: The YouTube video title

    Returns:
        Call number as integer, or None if not found
    """
    import re

    # Try patterns: "Call #10", "#10", "Call #10:"
    patterns = [
        r'Call\s+#(\d+)',
        r'#(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def get_latest_call_number(playlist_id: str, timeout: int = 5) -> int:
    """
    Get the call number from the latest video in the playlist.
    The next call number = latest call number + 1.

    Args:
        playlist_id: The YouTube playlist ID
        timeout: Timeout for yt-dlp in seconds (to avoid hanging)

    Returns:
        Next call number (latest + 1), or 1 as fallback
    """
    try:
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "playlistend": 1,
            "socket_timeout": timeout,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(playlist_url, download=False)

            if not result or "entries" not in result:
                logger.warning(f"Could not fetch latest video from playlist {playlist_id}")
                return 1

            entries = list(result["entries"])
            if not entries:
                logger.warning(f"Playlist {playlist_id} is empty")
                return 1

            video = entries[0]
            title = video.get("title", "")
            call_num = get_call_number_from_title(title)

            if call_num is not None:
                logger.info(f"Found call number {call_num} in latest video: {title}")
                return call_num + 1

            logger.warning(f"Could not extract call number from title: {title}")
            return 1

    except Exception as e:
        logger.warning(f"Error fetching playlist call number: {e}")
        return 1


if __name__ == "__main__":
    # Test the functions
    logging.basicConfig(level=logging.INFO)

    playlist_id = "PLn2qRQUAAg0zFWTWeuZVo05tUnOGAmWkm"
    print(f"Fetching latest video from playlist {playlist_id}...")

    video = get_latest_video_from_playlist(playlist_id)
    if video:
        print(f"\nTitle: {video.title}")
        print(f"URL: {video.url}")
        print(f"Upload Date: {video.upload_date}")
        print(f"\nSummary:\n{video.summary}")
    else:
        print("Failed to fetch video")
