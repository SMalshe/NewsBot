# main.py — the morning briefing job.
# Runs ONCE and exits. Scheduling is handled externally by GitHub Actions
# (see .github/workflows/briefing.yml). For each active subscriber it pulls
# news for their topics, summarizes with Claude, and texts them via Twilio.
#
# Inbound replies are NOT handled here — they run as a Twilio Function
# (twilio-function/functions/sms.js) triggered when someone texts the number.
from scraper import get_news
from summarizer import summarize, send_texts
from db import get_active_subscribers


def run():
    subscribers = get_active_subscribers()
    print(f"Sending briefings to {len(subscribers)} subscriber(s)")

    for phone, topics in subscribers:
        try:
            news = get_news(topics)
            stories, _ = summarize(news)
            send_texts(stories, phone)
            print(f"  ✓ sent to {phone} ({len(stories)} stories)")
        except Exception as e:
            print(f"  ✗ failed for {phone}: {e}")


if __name__ == "__main__":
    run()
