# actions/youtube.py
import re
import webbrowser
from core.voice import speak
from core.engine import raw_query
from core.logger import log

# ── Session state for follow-up ────────────────────────────────
# Stores last summarized video so "give me the long summary"
# works without repeating the URL
_last_video_id:    str = ""
_last_transcript:  str = ""
_last_video_title: str = ""


# ── URL + Video ID helpers ─────────────────────────────────────

def _extract_video_id(text: str) -> str:
    """Extract YouTube video ID from any URL format or plain text."""
    patterns = [
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""

def _get_transcript(video_id: str) -> str:
    """
    Fetch YouTube transcript. Handles both old (<0.6) and new (>=0.6)
    youtube-transcript-api versions.

    v0.6+ changed get_transcript from class method → instance method.
    Error 'has no attribute get_transcript' = new version installed.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # Always use instance (works for both old and new API)
        ytt = YouTubeTranscriptApi()

        # ── Try English first ──
        for lang_prefs in (["en", "en-US", "en-GB"], None):
            try:
                if lang_prefs:
                    raw = ytt.get_transcript(video_id, languages=lang_prefs)
                else:
                    # Any language — iterate TranscriptList and fetch first
                    transcript_list = ytt.list_transcripts(video_id)
                    first = next(iter(transcript_list))
                    raw   = first.fetch()

                # Handle both dict entries and object-style entries (new API)
                parts = []
                for entry in raw:
                    if isinstance(entry, dict):
                        parts.append(entry.get("text", ""))
                    else:
                        parts.append(getattr(entry, "text", str(entry)))
                return " ".join(parts)

            except StopIteration:
                return ""       # no transcripts at all
            except Exception:
                continue        # try next lang preference

        return ""
    except Exception as e:
        log.warning(f"[YouTube] Transcript error: {type(e).__name__}: {e}")
        return ""


def _get_video_info_ytdlp(video_id: str) -> dict:
    """
    Fallback: get video title + description via yt-dlp.
    Used when transcript is unavailable (private, no captions, etc.)
    """
    try:
        import yt_dlp
        url  = f"https://www.youtube.com/watch?v={video_id}"
        opts = {
            "quiet":         True,
            "no_warnings":   True,
            "skip_download": True,
            "extract_flat":  False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "title":       info.get("title", ""),
            "description": (info.get("description") or "")[:2000],
            "channel":     info.get("uploader", ""),
            "duration":    info.get("duration", 0),
            "view_count":  info.get("view_count", 0),
        }
    except Exception as e:
        log.warning(f"[YouTube] yt-dlp info failed: {e}")
        return {}


def _summarize_content(video_id: str, brief: bool = True) -> str:
    """
    Core summarization function. Returns spoken summary or error message.
    Tries transcript first, falls back to video info/description.
    """
    global _last_video_id, _last_transcript, _last_video_title

    # ── Transcript path (preferred — actual spoken content) ──
    transcript = _get_transcript(video_id)
    if transcript:
        _last_video_id   = video_id
        _last_transcript = transcript

        sentences = 3 if brief else 8
        instruction = (
            f"Summarize this YouTube video transcript in {sentences} clear spoken sentences. "
            f"Cover: what the video is about, the main points, and key takeaways. "
            f"No markdown, no bullet points — spoken format only."
        ) if not brief else (
            f"Summarize this YouTube video in 3-4 spoken sentences. "
            f"What is it about and what are the key points? No markdown."
        )

        summary = raw_query(
            f"{instruction}\n\nTranscript (first 4000 chars):\n{transcript[:4000]}",
            system=(
                "You are a concise video summarizer for a voice assistant. "
                "Output only the spoken summary — no introductions, no markdown."
            )
        )
        return summary or "I was unable to generate a summary for this video."

    # ── yt-dlp fallback (description-based) ──
    info = _get_video_info_ytdlp(video_id)
    if info:
        _last_video_id   = video_id
        _last_video_title = info.get("title", "")
        title       = info.get("title", "this video")
        channel     = info.get("channel", "")
        description = info.get("description", "")
        duration    = info.get("duration", 0)
        dur_str     = f"{duration // 60} minutes" if duration else ""

        if description:
            summary = raw_query(
                f"Summarize this YouTube video in 3-4 spoken sentences based on its metadata.\n"
                f"Title: {title}\n"
                f"Channel: {channel}\n"
                f"Duration: {dur_str}\n"
                f"Description: {description[:1500]}",
                system=(
                    "You are a video summarizer. Summarize based on the metadata provided. "
                    "No markdown, spoken format only."
                )
            )
            return summary or f"This video is titled '{title}' by {channel}."
        else:
            return (
                f"The video is titled '{title}'"
                f"{f' by {channel}' if channel else ''}. "
                f"No transcript or description is available for a detailed summary."
            )

    return (
        "I couldn't access this video's content. It may be private, "
        "age-restricted, or have no captions available."
    )


# ── Triggers ───────────────────────────────────────────────────

TRIGGERS = (
    "youtube", "play video", "watch", "video of",
    "summarize video", "summarise video", "transcript of",
    "trending videos", "trending on youtube",
    "youtu.be", "youtube.com",    # URL triggers
    "long summary", "detailed summary", "full summary",
)

_SUMMARIZE_TRIGGERS = (
    "summarize", "summarise", "summary", "transcript",
    "what is this video", "what does this video",
    "tell me about this video",
)

_LONG_SUMMARY_TRIGGERS = (
    "long summary", "detailed summary", "full summary",
    "more detail", "tell me more", "expand", "in detail",
    "longer", "yes", "yes please",
)


def handle_youtube(command: str) -> bool:
    global _last_video_id, _last_transcript

    # IMPORTANT: use original command for URL matching (case-sensitive video IDs)
    # Only lowercase for keyword trigger checks
    c = command.lower().strip()

    if not any(t in c for t in TRIGGERS):
        return False

    # ── Long summary follow-up ──────────────────────────────────
    if any(t in c for t in _LONG_SUMMARY_TRIGGERS) and _last_video_id:
        speak("Generating detailed summary. One moment.")
        summary = _summarize_content(_last_video_id, brief=False)
        speak(summary)
        return True

    # ── URL-based summarization ─────────────────────────────────
    # Use ORIGINAL command (not lowercased c) — YouTube IDs are case-sensitive
    # gpqsujnsnm0 ≠ GpQSUjNsNm0 — only the original is valid
    video_id = _extract_video_id(command)
    if video_id:
        speak("Got the link. Fetching the video content now.")
        summary = _summarize_content(video_id, brief=True)
        speak(summary)
        # Always offer the longer version
        speak("Say 'long summary' or 'tell me more' if you want a detailed breakdown.")
        return True

    # ── Summarize by search query ────────────────────────────────
    if any(t in c for t in _SUMMARIZE_TRIGGERS):
        query_text = c
        for filler in sorted(_SUMMARIZE_TRIGGERS, key=len, reverse=True):
            query_text = query_text.replace(filler, "")
        query_text = query_text.strip().strip(".,!?")

        if not query_text:
            speak(
                "Please share the YouTube link and I will summarize it for you. "
                "You can paste the URL directly."
            )
            return True

        speak(f"Searching YouTube for {query_text}.")
        try:
            import requests
            search_url = (
                f"https://www.youtube.com/results"
                f"?search_query={query_text.replace(' ', '+')}"
            )
            resp     = requests.get(search_url, timeout=8)
            ids      = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
            ids      = list(dict.fromkeys(ids))[:3]   # deduplicate, first 3
            video_id = ids[0] if ids else ""

            if not video_id:
                speak(f"I couldn't find a video for '{query_text}'.")
                return True

            summary = _summarize_content(video_id, brief=True)
            speak(summary)
            speak("Say 'long summary' if you want more detail.")

        except Exception as e:
            log.error(f"[YouTube Search Error] {e}")
            speak(
                "I couldn't search YouTube right now. "
                "Try pasting the video link directly."
            )
        return True

    # ── Trending ────────────────────────────────────────────────
    if "trending" in c:
        speak("Opening YouTube trending page.")
        webbrowser.open("https://www.youtube.com/feed/trending")
        return True

    # ── Open / Play ─────────────────────────────────────────────
    search_query = c
    for filler in sorted([
        "play on youtube", "search on youtube", "youtube search",
        "play video of", "play video", "watch video",
        "on youtube", "youtube", "watch", "play"
    ], key=len, reverse=True):
        search_query = search_query.replace(filler, "")
    search_query = search_query.strip()

    if search_query:
        speak(f"Playing {search_query} on YouTube.")
        webbrowser.open(
            f"https://www.youtube.com/results"
            f"?search_query={search_query.replace(' ', '+')}"
        )
    else:
        speak("Opening YouTube.")
        webbrowser.open("https://www.youtube.com")

    return True