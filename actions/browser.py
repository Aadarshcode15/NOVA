# actions/browser.py
import re
import time
import queue
import threading

from actions.base_action import BaseAction, ActionResult
from config.settings import BASE_DIR
from core.logger import log

# ── Persistent browser profile ──────────────────────────────
# Logins (LinkedIn, Amazon, etc.) persist across NOVA restarts —
# same as a normal Chrome profile. Lives in its own folder so it
# never touches your personal Chrome data.
PROFILE_DIR = BASE_DIR / "data" / "browser_profile"

# ── Worker thread — sole owner of Playwright ────────────────
# Playwright's sync API is thread-affined: every call must run on
# the exact thread that created the Playwright instance. Pattern
# mirrors the TTS worker — jobs go in via a queue, results come
# back via a per-job Event, so callers from any thread can use it.

_job_queue:     queue.Queue      = queue.Queue()
_worker_thread: threading.Thread = None
_worker_lock                     = threading.Lock()

_playwright = None
_context    = None   # persistent BrowserContext
_page       = None


def _ensure_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(
                target=_browser_worker, daemon=True, name="Browser-Worker"
            )
            _worker_thread.start()


def _browser_worker() -> None:
    """Lives for the app's lifetime. Owns every Playwright object."""
    global _playwright
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        _playwright = p
        while True:
            fn, args, holder, done = _job_queue.get()
            try:
                holder["result"] = fn(*args)
            except Exception as e:
                holder["error"] = e
            done.set()


def _run(fn, *args, timeout: float = 25.0):
    """Submit a job to the browser thread, block until it's done."""
    _ensure_worker()
    holder: dict = {}
    done = threading.Event()
    _job_queue.put((fn, args, holder, done))
    if not done.wait(timeout=timeout):
        raise TimeoutError("Browser action took too long.")
    if "error" in holder:
        raise holder["error"]
    return holder.get("result")


# ── Primitives — run INSIDE the worker thread only ──────────

def _get_context():
    global _context
    if _context is None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        _context = _playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
    return _context


def _get_page():
    global _page
    ctx = _get_context()
    if _page is None or _page.is_closed():
        _page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return _page


# Common search box patterns — tried in order, works across most sites
_SEARCH_SELECTORS = [
    'input[name="q"]',
    '#twotabsearchtextbox',          # Amazon
    'input[type="search"]',
    '[role="searchbox"]',
    'input[placeholder*="Search" i]',
]


def _do_navigate(url: str) -> str:
    page = _get_page()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return page.title()


def _do_search_on_site(site_url: str, query: str) -> dict:
    page = _get_page()
    page.goto(site_url, wait_until="domcontentloaded", timeout=15000)
    for selector in _SEARCH_SELECTORS:
        try:
            box = page.locator(selector).first
            if box.count() > 0:
                box.click(timeout=3000)
                box.fill(query)
                box.press("Enter")
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                time.sleep(1.2)   # let dynamic results render
                break
        except Exception:
            continue
    try:
        text = page.inner_text("body")[:3000]
    except Exception:
        text = ""
    return {"title": page.title(), "text": text}


def _do_extract_text() -> str:
    page = _get_page()
    try:
        return page.inner_text("body")[:3000]
    except Exception:
        return ""


def _do_click_text(text: str) -> bool:
    page = _get_page()
    page.get_by_text(text, exact=False).first.click(timeout=5000)
    page.wait_for_load_state("domcontentloaded", timeout=8000)
    return True


def _do_close() -> bool:
    global _context, _page
    if _context:
        try:
            _context.close()
        except Exception:
            pass
    _context = None
    _page    = None
    return True


# ── Known sites ───────────────────────────────────────────

KNOWN_SITES = {
    "amazon":         "https://www.amazon.in",
    "flipkart":       "https://www.flipkart.com",
    "linkedin":       "https://www.linkedin.com",
    "github":         "https://github.com",
    "wikipedia":      "https://www.wikipedia.org",
    "google flights": "https://www.google.com/travel/flights",
}


def _detect_site(text: str) -> tuple:
    for name, url in KNOWN_SITES.items():
        if name in text:
            return name, url
    return None, None


def _extract_search_query(text: str, site_name: str = None) -> str:
    q = text.lower()
    phrases = (
        [f"search on {site_name} for", f"search {site_name} for",
         f"search on {site_name}", f"search {site_name}",
         f"find jobs on {site_name} for", f"jobs on {site_name} for",
         f"find jobs on {site_name}", f"jobs on {site_name}",
         f"on {site_name}", "search for", "search"]
        if site_name else ["search for", "search"]
    )
    for phrase in sorted(set(phrases), key=len, reverse=True):
        q = q.replace(phrase, " ")
    return re.sub(r"\s+", " ", q).strip()


def _summarize_page(query: str, page_text: str) -> str:
    if not page_text or len(page_text.strip()) < 60:
        return "I've opened the results for you to look at."
    from core.engine import raw_query
    summary = raw_query(
        f"This is text extracted from a search results page for '{query}':\n\n"
        f"{page_text[:2500]}\n\n"
        f"Give a 2-sentence spoken summary of the most relevant items found. "
        f"No markdown, no bullet points.",
        system=(
            "You summarize web page content for a voice assistant. "
            "Be brief, natural, and specific where possible."
        )
    )
    return summary or "I've opened the results for you to look at."


# ── Triggers ──────────────────────────────────────────────
# Deliberately specific — avoids stealing "search for X" from
# web_search.py and "open google/youtube" from system_control.py.

TRIGGERS = (
    "browse to", "open the browser", "open browser",
    "search amazon", "search on amazon", "amazon for",
    "search flipkart", "search on flipkart", "flipkart for",
    "search linkedin", "search on linkedin", "linkedin for",
    "find jobs on linkedin", "jobs on linkedin",
    "search github", "search on github",
    "close browser", "close the browser",
    "what's on this page", "what is on this page",
    "summarize this page", "read this page",
    "click on", "click the",
)

_CLOSE     = ("close browser", "close the browser")
_PAGE_INFO = ("what's on this page", "what is on this page",
              "summarize this page", "read this page")
_CLICK     = ("click on", "click the")


class BrowserAction(BaseAction):
    """
    Browser automation via Playwright, persistent Chrome profile.

    Scope is deliberately narrow: site search, navigation, simple
    clicks, page summaries. Sites with heavy anti-bot protection or
    unusual DOM structure may not always cooperate — that's a
    reality of web automation, not something voice control alone
    can fix. The browser stays visible so you can always take over
    manually if NOVA gets stuck.
    """

    MAX_RETRIES = 1   # browser ops are slow — cap retries to bound latency

    def can_handle(self, command: str, intent: dict) -> bool:
        c = command.lower()
        return (
            intent.get("category") == "browser" or
            any(t in c for t in TRIGGERS)
        )

    def execute(self, command: str, context: dict) -> ActionResult:
        c = command.lower()

        # ── Close ──────────────────────────────────────────
        if any(t in c for t in _CLOSE):
            _run(_do_close)
            return ActionResult(True, "Closed the browser.")

        # ── Summarize current page ───────────────────────────
        if any(t in c for t in _PAGE_INFO):
            text    = _run(_do_extract_text)
            summary = _summarize_page("this page", text)
            return ActionResult(True, summary)

        # ── Click ──────────────────────────────────────────
        if any(t in c for t in _CLICK):
            target = c
            for t in sorted(_CLICK, key=len, reverse=True):
                target = target.replace(t, "")
            target = target.strip().strip(".,!?")
            if not target:
                return ActionResult(True, "What should I click on?")
            try:
                _run(_do_click_text, target)
                return ActionResult(True, f"Clicked {target}.")
            except Exception as e:
                log.warning(f"[Browser] Click failed for '{target}': {e}")
                return ActionResult(True, f"I couldn't find anything called {target} to click.")

        # ── Site search ───────────────────────────────────────
        site_name, site_url = _detect_site(c)
        if site_name and "search" in c:
            query = _extract_search_query(c, site_name)
            if not query:
                return ActionResult(True, f"What should I search for on {site_name.title()}?")
            result  = _run(_do_search_on_site, site_url, query)
            summary = _summarize_page(query, result.get("text", ""))
            return ActionResult(True, f"Searching {site_name.title()} for {query}. {summary}")

        # ── Open a known site directly ─────────────────────────
        if site_name:
            _run(_do_navigate, site_url)
            return ActionResult(True, f"Opened {site_name.title()}.")

        # ── Direct URL ("browse to github.com/x") ───────────────
        url_match = re.search(r'(https?://\S+|\b[\w-]+\.(?:com|org|net|in|io)\b\S*)', c)
        if url_match:
            url = url_match.group(0)
            if not url.startswith("http"):
                url = "https://" + url
            title = _run(_do_navigate, url)
            return ActionResult(True, f"Opened {title or url}.")

        return ActionResult(
            True,
            "Which website should I open? You can also say things like "
            "search Amazon for wireless earbuds."
        )


# ── Module-level handler for router compatibility ────────────
_browser_action = BrowserAction()

def handle_browser(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False
    return _browser_action.handle(command)