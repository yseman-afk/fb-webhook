from flask import Flask, request
import requests
import os
import datetime

app = Flask(__name__)

PAGE_TOKEN = os.getenv("PAGE_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def send_fb_message(user_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_TOKEN}
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text}
    }
    requests.post(url, params=params, json=payload)


def call_ai_agent(message_text, profile_data):
    url = "https://api.openai.com/v1/chat/completions"

    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.weekday()

    ai_rules = (
        "Follow these rules exactly:\n"
        "1. Ignore profiles less than 7 days old.\n"
        "2. Detect Spanish. If Spanish, answer in Spanish.\n"
        "3. If they ask 'is it available' (or similar):\n"
        "   - If Friday after 18:00 or Saturday: reply 'When can you meet Sunday?'\n"
        "   - Else if hour >= 20: reply 'When can you meet tomorrow?'\n"
        "   - Else reply 'When can you meet today?'\n"
        "4. If ignoring, reply exactly: ignore\n"
    )

    data = {
        "model": "gpt-5",
        "messages": [
            {"role": "system", "content": ai_rules},
            {
                "role": "user",
                "content": str({
                    "message": message_text,
                    "profile": profile_data,
                    "hour": hour,
                    "weekday": weekday
                })
            }
        ]
    }

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    r = requests.post(url, json=data, headers=headers)
    return r.json()["choices"][0]["message"]["content"].strip()


@app.route("/", methods=["GET"])
def home():
    return "Running"


@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verification failed"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        msg = data["entry"][0]["messaging"][0]
        sender = msg["sender"]["id"]
        text = msg.get("message", {}).get("text", "")

        # profile lookup
        profile = requests.get(
            f"https://graph.facebook.com/{sender}",
            params={
                "fields": "created_time",
                "access_token": PAGE_TOKEN
            }
        ).json()

        reply = call_ai_agent(text, profile)

        if reply.lower() != "ignore":
            send_fb_message(sender, reply)

    except Exception as e:
        print("ERROR:", e)

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
