# actions/whatsapp.py
import json
import re
import pywhatkit
from core.voice import speak
from config.settings import CONTACTS_FILE


def _load_contacts() -> dict:
    try:
        if CONTACTS_FILE.exists():
            return json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WhatsApp] Contacts load error: {e}")
    return {}


TRIGGERS = ("whatsapp", "message", "send", "text")


def handle_whatsapp(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    contacts = _load_contacts()
    if not contacts:
        speak("No contacts found. Please add contacts to config/contacts.json.")
        return True

    # ── Find contact — whole-word match only ──────────────────
    # OLD BUG: "ag" in "message" matched "messAGe"
    # FIX: \b word boundary ensures "ag" only matches as standalone word
    contact_name   = None
    contact_number = None
    for name, number in contacts.items():
        if re.search(r'\b' + re.escape(name.lower()) + r'\b', c):
            contact_name   = name
            contact_number = number
            break

    if not contact_number:
        speak("I didn't recognise that contact. Please add them to your contacts file.")
        return True

    # ── Extract message ───────────────────────────────────────
    # Find where the contact name ends in the string (using lowercased c,
    # but positions are identical in original command since lower() keeps length)
    match = re.search(r'\b' + re.escape(contact_name.lower()) + r'\b', c)
    if not match:
        speak(f"What would you like to say to {contact_name}?")
        return True

    # Slice original command from after the contact name
    after_contact = command[match.end():].strip()

    # Strip connector words at the start of the message
    for prefix in sorted([
        "saying that", "saying", "to say that", "to say",
        "with the message", "with", "that", ":"
    ], key=len, reverse=True):
        if after_contact.lower().startswith(prefix):
            after_contact = after_contact[len(prefix):].strip()
            break

    message = after_contact.strip()

    if not message:
        speak(f"What would you like to say to {contact_name}?")
        return True

    speak(f"Sending message to {contact_name}.")
    try:
        pywhatkit.sendwhatmsg_instantly(
            contact_number,
            message,
            wait_time=15,
            tab_close=True,
            close_time=5
        )
        speak("Message sent.")
    except Exception as e:
        print(f"[WhatsApp Send Error] {e}")
        speak("Message may not have sent. Make sure WhatsApp Web is logged in on your browser.")
    return True