# actions/weather_news.py
import requests
from core.voice import speak
from config.settings import WEATHER_API_KEY, NEWS_API_KEY, MAX_NEWS

NEWS_CATEGORIES = {
    "technology":    "technology",
    "tech":          "technology",
    "sport":         "sports",
    "sports":        "sports",
    "cricket":       "sports",
    "football":      "sports",
    "business":      "business",
    "finance":       "business",
    "economy":       "business",
    "health":        "health",
    "medical":       "health",
    "science":       "science",
    "space":         "science",
    "entertainment": "entertainment",
    "movies":        "entertainment",
    "bollywood":     "entertainment",
    "general":       "general",
    "world":         "general",
    "top":           "general",
}

# ── Weather ───────────────────────────────────────────────
def handle_weather(command: str) -> bool:
    if "weather" not in command:
        return False
    try:
        loc  = requests.get("http://ip-api.com/json/", timeout=5).json()
        city = loc.get("city", "your location")
        if not WEATHER_API_KEY:
            speak("Weather API key not set. Please add it to your .env file.")
            return True
        url  = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={WEATHER_API_KEY}&units=metric"
        )
        data  = requests.get(url, timeout=5).json()
        temp  = round(data["main"]["temp"])
        feels = round(data["main"]["feels_like"])
        desc  = data["weather"][0]["description"]
        hum   = data["main"]["humidity"]
        speak(
            f"In {city}, it is {temp} degrees Celsius with {desc}. "
            f"Feels like {feels} degrees, humidity at {hum} percent."
        )
    except Exception as e:
        print(f"[Weather Error] {e}")
        speak("Sorry, I couldn't fetch the weather right now.")
    return True

# ── News ──────────────────────────────────────────────────
def _fetch_news(category: str = "general") -> None:
    try:
        if not NEWS_API_KEY:
            speak("News API key not set. Please add it to your .env file.")
            return
        url = (
            f"https://gnews.io/api/v4/top-headlines"
            f"?category={category}&lang=en&country=in"
            f"&max={MAX_NEWS}&apikey={NEWS_API_KEY}"
        )
        articles = requests.get(url, timeout=5).json().get("articles", [])
        if not articles:
            speak(f"No {category} news found right now.")
            return
        label = category.capitalize() if category != "general" else "top"
        speak(f"Here are {len(articles)} {label} headlines.")
        for i, a in enumerate(articles, 1):
            speak(f"Headline {i}. {a['title']}")
    except Exception as e:
        print(f"[News Error] {e}")
        speak("Couldn't fetch the news.")

def handle_news_command(command: str) -> bool:
    triggers = ("news", "headlines", "headline")
    if not any(t in command for t in triggers):
        return False
    detected = "general"
    for keyword in sorted(NEWS_CATEGORIES.keys(), key=len, reverse=True):
        if keyword in command:
            detected = NEWS_CATEGORIES[keyword]
            break
    _fetch_news(detected)
    return True