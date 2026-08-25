# N.O.V.A — Command Reference

**Neural Operative Virtual Assistant**
Complete list of voice commands and capabilities.

---

## Table of Contents

- [Wake & Sleep](#wake--sleep)
- [System Control](#system-control)
- [Music (Spotify)](#music-spotify)
- [Communication](#communication)
- [Calendar](#calendar)
- [Browser Automation](#browser-automation)
- [YouTube](#youtube)
- [Code Helper](#code-helper)
- [File Upload & Analysis](#file-upload--analysis)
- [Smart Clipboard](#smart-clipboard)
- [Memory](#memory)
- [Voice Journal](#voice-journal)
- [Command Macros / Routines](#command-macros--routines)
- [Morning Briefing](#morning-briefing)
- [Reminders & To-Do](#reminders--to-do)
- [Weather & News](#weather--news)
- [Screen Vision](#screen-vision)
- [Language & Persona](#language--persona)
- [Utility](#utility)
- [Automatic Features](#automatic-features)

---

## Wake & Sleep

NOVA is active for 5 minutes on startup, then auto-sleeps until called again.

| Command | Action |
|---|---|
| `Nova` | Wakes NOVA from sleep mode |
| `Nova sleep` | Puts NOVA to sleep immediately |
| `Nova stop` | Same as above |

---

## System Control

| Command | Action |
|---|---|
| `Open Chrome` / `Spotify` / `WhatsApp` / `VS Code` / `Notepad` / `Excel` | Opens common apps |
| `Open [any app name]` | Falls back to Windows search if not preconfigured |
| `Volume up` / `Volume down` | Adjusts system volume |
| `Set volume to 50` | Sets exact volume level |
| `Mute` / `Unmute` | Toggles mute |
| `Brightness up` / `Brightness down` | Adjusts screen brightness |
| `Set brightness to 70` | Sets exact brightness level |
| `Take a screenshot` | Captures and saves a screenshot |
| `Check battery` | Reports battery status |
| `What time is it` | Reports current time |
| `What's the date` | Reports current date |

---

## Music (Spotify)

| Command | Action |
|---|---|
| `Play [song/artist]` | Plays specific track |
| `Play something chill` | Mood-based playback |
| `Pause music` / `Resume music` | Playback control |
| `Next song` / `Previous song` | Skip tracks |
| `What's playing` | Reports current track |

---

## Communication

| Command | Action |
|---|---|
| `Message [contact] saying [text]` | Sends WhatsApp message |
| `Check my emails` / `Any new emails` | Lists unread emails |
| `Summarize that email` | Summarizes most recent/specified email |
| `Find emails from [name]` | Searches inbox |
| `Send an email to [contact] saying [message]` | Composes and sends |

---

## Calendar

| Command | Action |
|---|---|
| `What's on my calendar today` | Lists today's events |
| `My schedule tomorrow` | Lists tomorrow's events |
| `Schedule a meeting with [name] tomorrow at 3 PM` | Creates event |
| `What's my next meeting` | Reports next upcoming event |

---

## Browser Automation

| Command | Action |
|---|---|
| `Search Amazon for [product]` | Opens Amazon and searches |
| `Search LinkedIn for [job title]` | Opens LinkedIn and searches |
| `Browse to [website]` | Navigates to a URL |
| `What's on this page` / `Summarize this page` | Summarizes current browser page |
| `Click on [text]` | Clicks matching element |
| `Close the browser` | Closes automated browser session |

---

## YouTube

| Command | Action |
|---|---|
| `Play [video] on YouTube` | Searches and opens |
| *(paste a YouTube link directly)* | Auto-summarized in 3–4 sentences |
| `Long summary` | Follow-up for a more detailed breakdown |
| `Trending on YouTube` | Opens trending page |

---

## Code Helper

All code is saved to a **Nova Code Helper** folder on your Desktop, with automatic backups before any fix.

| Command | Action |
|---|---|
| `Write code for [task]` | Generates code |
| `Build a calculator in Python` | Natural-language code generation |
| `Create an HTML page with a login form` | Web page generation |
| `List my codes` | Lists saved files |
| `Run the code` | Executes most recent/specified file |
| `Explain the code` | Explains what a file does |
| `Fix the code` | Debugs and repairs, with backup |

---

## File Upload & Analysis

Drag and drop, or click to upload. NOVA auto-analyzes on upload:

- **Images** — vision description + OCR text extraction
- **PDFs** — text extraction with OCR fallback for scanned documents
- **Word documents** — full text + table extraction
- **Excel files** — sheet and cell data extraction
- **Code files** — language detection + line count
- **Text files** — word count + preview

| Follow-up command | Action |
|---|---|
| `Summarize it` | Summarizes the uploaded file |
| `Explain it` | Explains code files |
| `Fix it` | Debugs code files |
| `Read the text` | Reads extracted text aloud |

---

## Smart Clipboard

Activates only when explicitly requested — no background monitoring.

| Command | Action |
|---|---|
| `See the clipboard` / `What did I copy` | Analyzes current clipboard content |

**Follow-ups after activation:**

| Command | Action |
|---|---|
| `Open it` | Opens a copied link |
| `Summarize it` | Summarizes copied text/page |
| `Explain it` | Explains copied code |
| `Fix it` | Debugs copied code |
| `Save it` | Saves code to Nova Code Helper |
| `Translate it` | Translates copied text |

---

## Memory

| Command | Action |
|---|---|
| `Remember that [fact]` | Saves a personal fact |
| `What do you know about me` | Recalls stored memory |
| `Forget [thing]` | Removes a specific memory |

---

## Voice Journal

| Command | Action |
|---|---|
| `Add a voice note` | Starts recording, then captures next speech |
| `Add a voice note: buy milk` | Inline note, saved immediately |
| `Read my journal` | Reads today's entries |
| `What did I note yesterday` | Reads yesterday's summary |

---

## Command Macros / Routines

| Command | Action |
|---|---|
| `Record morning routine` | Starts recording a command sequence |
| *(speak each step)* | Captured, not executed, while recording |
| `Stop recording` | Saves the routine |
| `Run morning routine` | Executes all recorded steps in sequence |
| `List my routines` | Lists all saved routines |

---

## Morning Briefing

| Command | Action |
|---|---|
| `Morning briefing` | Manually triggers the briefing |

Runs automatically every day at your configured time — set in **Settings → Briefing**.

---

## Reminders & To-Do

| Command | Action |
|---|---|
| `Remind me to [task] at [time]` | Sets a scheduled reminder |
| `Remind me in 30 minutes` | Relative-time reminder |
| `Add [item] to my to-do list` | Adds a task |
| `Show my tasks` | Lists all to-do items |

---

## Weather & News

| Command | Action |
|---|---|
| `What's the weather` | Current weather for your location |
| `Tech news` / `Sports news` | Category headlines |

---

## Screen Vision

| Command | Action |
|---|---|
| `What's on my screen` / `Describe my screen` | Describes current screen content |

---

## Language & Persona

| Command | Action |
|---|---|
| `Switch to Hindi` | Responds in Romanized Hindi |
| `Switch to Marathi` | Responds in Romanized Marathi |
| `Switch to English` | Returns to English |
| `Switch to Sora` | Switches to SORA persona (female voice) |
| `Switch to Nova` | Switches back to NOVA (male voice) |

---

## Utility

| Command | Action |
|---|---|
| `Open settings` | Opens the settings panel |
| `Search my history for [topic]` | Searches past conversations |
| `Performance stats` | Reports response time statistics |
| `Switch to Gemini` / `Groq` / `Ollama` | Manually overrides the AI engine |

---

## Automatic Features

These require no command — they run in the background:

- **Proactive alerts** — spoken warnings for low battery, high RAM, low disk space, or high CPU/temperature (only while NOVA is active)
- **Windows auto-start** — toggle in **Settings → General**

---

*Generated for N.O.V.A — Neural Operative Virtual Assistant*
