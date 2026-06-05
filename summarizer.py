# summarize.py
import os, anthropic, json, re
from twilio.rest import Client

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

SYSTEM = """You are a sharp, slightly sensationalist news reporter. For each story, write a punchy 2-3 sentence SMS summary — dramatic, factual, opinionated. End each with a one-line question that makes the reader want to reply.

Return ONLY a valid JSON array, no other text:
[
  {
    "topic": "topic name",
    "summary": "2-3 punchy sentences. Key facts in CAPS for emphasis. (via Source) at end.",
    "question": "one provocative question?",
    "link": "url"
  }
]"""

def summarize(news):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    text = ""
    for topic, items in news.items():
        for it in items:
            text += f"Topic: {topic}\nTitle: {it['title']}\nSummary: {it['summary']}\nSource: {it.get('source', '')}\nLink: {it['link']}\n\n"

    raw = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Summarize these stories:\n\n{text}"}]
    ).content[0].text

    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    stories = json.loads(raw)

    # Also save a plain-text version for the responder
    briefing = "\n\n".join(
        f"{s['topic'].upper()}: {s['summary']} {s['question']}" for s in stories
    )
    return stories, briefing


def send_texts(stories):
    twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    from_num = os.environ["TWILIO_FROM_NUMBER"]
    to_num = os.environ["RECIPIENT_PHONE"]

    topics = list(dict.fromkeys(s["topic"].title() for s in stories))
    twilio.messages.create(
        body=f"☕ Morning Brew\nToday: {', '.join(topics)}",
        from_=from_num, to=to_num
    )

    for s in stories:
        body = f"📰 {s['topic'].upper()}\n{s['summary']}\n\n{s['question']}\n🔗 {s['link']}"
        twilio.messages.create(body=body, from_=from_num, to=to_num)