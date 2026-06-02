# actions/web_search.py
import webbrowser
import requests
from core.voice import speak
from core.engine import query

TRIGGERS = (
    "search for", "search", "look up", "find", "browse",
    "google", "what is", "who is", "how to", "tell me about"
)

def handle_search(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    # ── Open browser with search ──
    if any(k in c for k in ("google", "search for", "search")):
        q = c
        for filler in sorted(["search for", "search on google", "google search",
                               "search", "google"], key=len, reverse=True):
            q = q.replace(filler, "")
        q = q.strip()
        if q:
            speak(f"Searching for {q}.")
            webbrowser.open(f"https://www.google.com/search?q={q.replace(' ', '+')}")
        return True

    # ── AI-powered answer using DuckDuckGo + Gemini ──
    if any(k in c for k in ("what is", "who is", "how to", "tell me about", "look up", "find")):
        search_q = c
        for filler in sorted(["tell me about", "look up", "find out about",
                               "what is", "who is", "how to", "find"], key=len, reverse=True):
            search_q = search_q.replace(filler, "")
        search_q = search_q.strip()

        if not search_q:
            return False

        speak(f"Let me find that for you.")
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(search_q, max_results=3))
            if results:
                context = "\n".join([r.get("body", "") for r in results])
                answer  = query(
                    f"Based on this search result, answer in 2-3 spoken sentences "
                    f"(no markdown, no bullet points):\n"
                    f"Question: {search_q}\n"
                    f"Search results: {context[:2000]}"
                )
                speak(answer)
            else:
                speak(f"I couldn't find anything about {search_q}.")
        except Exception as e:
            print(f"[Search Error] {e}")
            speak("Sorry, I couldn't complete that search.")
        return True

    return False