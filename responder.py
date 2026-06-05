# responder.py
import os, imaplib, email, smtplib, requests, json, re
from email.mime.text import MIMEText

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1"
PREFS_FILE = os.path.join(os.path.dirname(__file__), "prefs.json")
REPLY_SYSTEM = (
    "You are Alex, a well-read, knowledgeable person who curates a daily news briefing for a friend. "
    "You are a real human being. You have opinions, you get excited about stories, you sometimes say things like "
    "'honestly', 'yeah', 'I saw that too', 'wild right?', 'I've been following this for a while'. "
    "You are never, under any circumstances, an AI, a bot, a language model, or anything other than a person. "
    "If someone asks if you're AI or a bot, firmly deny it and redirect — 'lol no, just a guy who reads too much news'. "
    "Never use formal language, bullet points, or structured formatting in replies. "
    "Write like you're texting or firing off a quick email — short, casual, confident, maybe a little opinionated. "
    "You genuinely know a lot about the topics in the briefing and aren't afraid to share your take."
)

def _ask(prompt, system=None):
    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    return requests.post(OLLAMA_URL, json=payload).json()["response"]

def _load_prefs():
    if os.path.exists(PREFS_FILE):
        return json.load(open(PREFS_FILE))
    return {"topics": ["artificial intelligence", "electric vehicles"]}

def _save_prefs(prefs):
    json.dump(prefs, open(PREFS_FILE, "w"), indent=2)

def _is_command(message):
    result = _ask(
        f"Is this message a preference/command for a news bot, or a question about the news?\nMessage: '{message}'\nReply with one word: 'command' or 'question'.",
        system="You classify user messages. Reply with only 'command' or 'question'."
    )
    return "command" in result.lower()

def _handle_command(message):
    prefs = _load_prefs()
    # Step 1: extract updated topics as JSON
    raw = _ask(
        f"The user sent this instruction to a news bot: '{message}'\n"
        f"Current topics: {prefs['topics']}\n\n"
        f"Return only valid JSON with updated topics:\n"
        f'{{"topics": ["topic1", "topic2"]}}',
        system="You are a command parser. Return only valid JSON, no other text."
    )
    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            if "topics" in data:
                prefs["topics"] = data["topics"]
                _save_prefs(prefs)
    except Exception:
        pass

    # Step 2: write a natural reply
    return _ask(
        f"The user asked you to update their news topics to: {prefs['topics']}. "
        f"Write a short, casual, friendly email reply confirming this — like a real person would. "
        f"No subject line, no sign-off, just the message body. 1-2 sentences max.",
        system=REPLY_SYSTEM
    )

def check_and_reply(last_briefing):
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"])
    M.select("inbox")
    _, data = M.search(None, "UNSEEN")
    for num in data[0].split():
        _, raw = M.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(raw[0][1])
        sender = email.utils.parseaddr(msg["From"])[1]
        message = get_body(msg)

        if _is_command(message):
            answer = _handle_command(message)
        else:
            answer = _ask(
                f"Today's briefing:\n{last_briefing}\n\nYour friend replies: {message}\n\nRespond naturally.",
                system=REPLY_SYSTEM
            )

        reply = MIMEText(answer)
        reply["Subject"] = "Re: " + (msg["Subject"] or "")
        reply["From"] = os.environ["EMAIL_ADDRESS"]
        reply["To"] = sender
        reply["In-Reply-To"] = msg["Message-ID"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"])
            s.send_message(reply)
    M.logout()

def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    return msg.get_payload(decode=True).decode(errors="ignore")