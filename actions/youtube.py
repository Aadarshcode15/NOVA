# actions/youtube.py
import webbrowser
from core.voice import speak
from core.engine import query
from core.logger import log

TRIGGERS = (
    "youtube", "play video", "watch", "video of",
    "summarize video", "summarise video", "transcript of",
    "trending videos", "trending on youtube"
)

def handle_youtube(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    # ── Trending ──
    if "trending" in c:
        speak("Opening YouTube trending page.")
        webbrowser.open("https://www.youtube.com/feed/trending")
        return True

    # ── Summarize video ──
    if any(k in c for k in ("summarize", "summarise", "transcript", "summary of")):
        query_text = c
        for filler in sorted([
            "summarize the video", "summarise the video",
            "give me a summary of", "summary of",
            "transcript of", "summarize", "summarise"
        ], key=len, reverse=True):
            query_text = query_text.replace(filler, "")
        query_text = query_text.strip()

        if not query_text:
            speak("Which video would you like me to summarize?")
            return True

        speak(f"Let me find and summarize that video.")
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            import requests
            # Search for video ID
            search_url = f"https://www.youtube.com/results?search_query={query_text.replace(' ', '+')}"
            resp       = requests.get(search_url, timeout=5)
            import re
            video_ids  = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", resp.text)
            if not video_ids:
                speak("Couldn't find that video on YouTube.")
                return True

            video_id = video_ids[0]
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([t["text"] for t in transcript_list])[:3000]

            summary = query(
                f"Summarize this YouTube video transcript in 3-4 spoken sentences. "
                f"No markdown or bullet points:\n\n{full_text}",
                skip_history=True
            )
            speak(summary)
        except Exception as e:
            log.error(f"[YouTube Summarize Error] {e}")
            speak("Sorry, I couldn't get the transcript for that video.")
        return True

    # ── Play / Search video ──
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
            f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
        )
    else:
        speak("Opening YouTube.")
        webbrowser.open("https://www.youtube.com")
    return True