import imaplib
import email
import time
import re
import os

# ================= CONFIG =================
EMAIL = "circuitsaga@gmail.com"
APP_PASSWORD = os.getenv("PASS")

IMAP_SERVER = "imap.gmail.com"
CHECK_INTERVAL = 5  # seconds

FAMPAY_SENDER = "no-reply@famapp.in"

import requests

PUSHCUT_URL = os.getenv("URL")
BASE_URL = os.getenv("RENDER")

def alert(amount, sender):
    text = f"You received rupees {amount} from {sender}"

    file_path = generate_voice(text)
    if not file_path:
        return

    filename = file_path.split("/")[-1]
    audio_url = f"{BASE_URL}/voice/{filename}"

    requests.post(
        PUSHCUT_URL,
        json={
            "title": "💰 Payment Received",
            "text": "Tap to hear payment voice",
            "url": audio_url
        },
        timeout=10
    )

    print("🚀 Pushcut sent with voice")

ELEVENLABS_API_KEY = os.getenv("API")
VOICE_ID = os.getenv("ID")


def generate_voice(text):

    filename = f"voice/payment_{uuid.uuid4().hex}.mp3"
    os.makedirs("voice", exist_ok=True)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2"
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        print("🔊 Voice generated")
    else:
        print("❌ ElevenLabs error:", response.text)

# ================= YOUR FUNCTION =================

from flask import Flask, send_from_directory

app = Flask(__name__)

@app.route("/voice/<path:filename>")
def serve_voice(filename):
    return send_from_directory("voice", filename)

def on_payment_received(amount, sender_name):
    print(f"\n🎉 PAYMENT RECEIVED!")
    print(f"Amount: ₹{amount}")
    print(f"Sender: {sender_name}\n")
    iamount = int(float(amount))
    text = f"You Have Received ₹{iamount} From {sender_name} Just Now! Thank You!"
    alert(text)

    
# ================= PARSER =================

def extract_payment_details(text):
    """
    Accurate FamPay parser
    Example line:
    received ₹1.0 from MAJIDA B at 08:29 AM
    """

    # ✅ Amount
    amount_match = re.search(r"₹\s?(\d+(?:\.\d+)?)", text)

    # ✅ Sender name (stops before ' at ')
    name_match = re.search(
        r"received\s+₹[\d\.]+\s+from\s+(.+?)\s+at",
        text,
        re.IGNORECASE
    )

    amount = amount_match.group(1) if amount_match else None
    sender_name = name_match.group(1).strip() if name_match else "Unknown"

    return amount, sender_name

# ================= MAIN CHECKER =================
def check_gmail():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, APP_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        mail_ids = messages[0].split()

        if not mail_ids:
            mail.logout()
            return

        # ✅ ONLY process latest unread
        latest_id = mail_ids[-1]

        status, msg_data = mail.fetch(latest_id, "(RFC822)")

        for response_part in msg_data:
            if not isinstance(response_part, tuple):
                continue

            msg = email.message_from_bytes(response_part[1])

            sender = msg.get("From", "")
            subject = msg.get("Subject", "")

            print("DEBUG sender:", sender)
            print("DEBUG subject:", subject)

            # ✅ Filter FamPay
            if FAMPAY_SENDER not in sender:
                print("Not FamPay mail, skipping.")
                continue

            # ===== Extract body =====
            body = ""

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            print("DEBUG body snippet:", body[:200])

            # ===== Extract payment =====
            amount, sender_name = extract_payment_details(body)

            if amount:
                on_payment_received(amount, sender_name)
                mail.store(latest_id, '+FLAGS', '\\Seen')

            else:
                print("⚠️ Could not extract payment info")

        mail.logout()

    except Exception as e:
        print("❌ Error:", e)


# ================= LOOP =================
def main():
    print("🚀 Gmail FamPay watcher started...")

    while True:
        check_gmail()
        time.sleep(CHECK_INTERVAL)

import threading

def run_web():
    app.run(host="0.0.0.0", port=10000)

threading.Thread(target=run_web).start()

if __name__ == "__main__":
    main()