# actions/whatsapp.py
import json
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

    # ── Find contact ──
    contact_name   = None
    contact_number = None
    for name, number in contacts.items():
        if name.lower() in c:
            contact_name   = name
            contact_number = number
            break

    if not contact_number:
        speak("I didn't recognise that contact. Please add them to your contacts file.")
        return True

    # ── Extract message ──
    msg_start = c.find(contact_name.lower()) + len(contact_name)
    message   = command[msg_start:].strip()

    for prefix in sorted([
        "saying that", "saying", "to say that", "to say",
        "with the message", "with", "that", ":"
    ], key=len, reverse=True):
        if message.lower().startswith(prefix):
            message = message[len(prefix):].strip()
            break

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