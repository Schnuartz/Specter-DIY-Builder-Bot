"""YouTube utilities for fetching playlist and video data."""

import yt_dlp
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
        """Extract a summary from the video description."""
        if not self.description:
return "No description available."

        # Take first 500 characters or until double newline
        desc = self.description.strip()

        # Try to find a natural break point
        if "\n\n" in desc[:500]:
            summary = desc[:desc.index("\n\n", 0, 500)]
        elif len(desc) > 500:
            # Find last sentence end before 500 chars
            last_period = desc[:500].rfind(".")
            if last_period > 100:
                summary = desc[:last_period + 1]
            else:
                summary = desc[:500] + "..."
        else:
            summary = desc

        return summary


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
