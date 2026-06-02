# actions/spotify.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from core.voice import speak
from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT

_sp        = None
_sp_failed = False

def _get_spotify():
    global _sp, _sp_failed
    if _sp_failed:
        return None
    if _sp is None:
        try:
            _sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT,
                scope="user-modify-playback-state user-read-playback-state user-read-currently-playing"
            ))
        except Exception as e:
            print(f"[Spotify Init Error] {e}")
            _sp_failed = True
    return _sp

TRIGGERS = (
    "spotify", "song", "music", "play ", "pause music",
    "stop music", "next song", "skip song", "previous song",
    "resume music", "what song", "current song", "what's playing"
)

def handle_spotify(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not connected. Please set your Spotify API keys in the config.")
        return True

    try:
        # ── What's playing ──
        if any(k in c for k in ("what song", "current song", "what's playing", "now playing")):
            current = sp.current_playback()
            if current and current.get("item"):
                track  = current["item"]["name"]
                artist = current["item"]["artists"][0]["name"]
                speak(f"Currently playing {track} by {artist}.")
            else:
                speak("Nothing is playing on Spotify right now.")
            return True

        # ── Pause / Stop ──
        if "pause" in c or ("stop" in c and "music" in c):
            sp.pause_playback()
            speak("Paused.")
            return True

        # ── Resume ──
        if any(k in c for k in ("resume", "continue", "unpause")):
            sp.start_playback()
            speak("Resuming.")
            return True

        # ── Next ──
        if any(k in c for k in ("next", "skip")):
            sp.next_track()
            speak("Next track.")
            return True

        # ── Previous ──
        if any(k in c for k in ("previous", "last song", "go back")):
            sp.previous_track()
            speak("Previous track.")
            return True

        # ── Volume ──
        if "spotify volume" in c or ("volume" in c and "spotify" in c):
            words = c.split()
            for w in words:
                if w.isdigit():
                    level = max(0, min(100, int(w)))
                    sp.volume(level)
                    speak(f"Spotify volume set to {level}.")
                    return True

        # ── Play a song / artist / playlist ──
        query = c
        for filler in sorted([
            "play on spotify", "on spotify", "play me", "spotify",
            "song", "music", "the song", "play"
        ], key=len, reverse=True):
            query = query.replace(filler, "")
        query = query.strip()

        if query:
            results = sp.search(q=query, limit=1, type="track")
            tracks  = results.get("tracks", {}).get("items", [])
            if tracks:
                uri         = tracks[0]["uri"]
                track_name  = tracks[0]["name"]
                artist_name = tracks[0]["artists"][0]["name"]
                sp.start_playback(uris=[uri])
                speak(f"Playing {track_name} by {artist_name}.")
            else:
                speak(f"Couldn't find {query} on Spotify.")

    except spotipy.exceptions.SpotifyException as e:
        print(f"[Spotify Error] {e}")
        speak("Spotify error. Make sure Spotify is open on a device.")
    except Exception as e:
        print(f"[Spotify Error] {e}")
        speak("Something went wrong with Spotify.")
    return True