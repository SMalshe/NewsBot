# db.py — Postgres access layer for subscribers.
# Used by the morning briefing job (GitHub Actions). The inbound-SMS reply
# handler lives separately as a Twilio Function (twilio-function/functions/sms.js)
# and talks to the same database.
import os
import psycopg2

DEFAULT_TOPICS = ["ai", "world"]


def _conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def get_active_subscribers():
    """Return a list of (phone, topics) for everyone currently subscribed."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT phone, topics FROM subscribers WHERE status = 'active'")
        return cur.fetchall()


def add_subscriber(phone, topics=None, consent_text=None):
    """Insert a subscriber (or re-activate one), recording consent."""
    topics = topics or DEFAULT_TOPICS
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO subscribers (phone, topics, status, consent_at, consent_text)
            VALUES (%s, %s, 'active', now(), %s)
            ON CONFLICT (phone)
            DO UPDATE SET status = 'active', consent_at = now(),
                          consent_text = EXCLUDED.consent_text
            """,
            (phone, topics, consent_text),
        )


def set_topics(phone, topics):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE subscribers SET topics = %s WHERE phone = %s", (topics, phone))


def set_status(phone, status):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE subscribers SET status = %s WHERE phone = %s", (status, phone))


def log_consent(phone, event, method=None, consent_text=None, ip=None, user_agent=None):
    """Append an immutable consent record. event is 'opt_in' or 'opt_out'.

    This is the audit trail SMS carriers may ask for as proof of consent.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO consent_log (phone, event, method, consent_text, ip, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (phone, event, method, consent_text, ip, user_agent),
        )
