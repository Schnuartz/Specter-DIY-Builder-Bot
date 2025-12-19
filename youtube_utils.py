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
        model = genai.GenerativeModel('gemini-pro')
        prompt = (
            "You are a helpful assistant for a software development community. "
            "Your task is to summarize the description of a YouTube video about a technical community call. "
            "The summary should be concise, in German, and highlight the main topics discussed. "
            "Focus on technical aspects, pull requests, and new features. Maximum 3-4 bullet points.\n\n"
            f"Please summarize this:\n\n{text}"
        )
        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return text[:500].strip() + "..." if len(text) > 500 else text


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


def get_latest_video_from_playlist(playlist_id: str) -> Optional[VideoInfo]:
    """
    Fetch the latest video from a YouTube playlist.

    Args:
        playlist_id: The YouTube playlist ID

    Returns:
        VideoInfo object or None if failed
    """
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "playlistend": 1,  # Only get the first (latest) video
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
