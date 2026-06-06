# News Bot — Setup & Deploy Guide

Two-way SMS news briefings. Three moving parts:

| Part | What it does | Where it runs |
|------|--------------|---------------|
| **Morning briefing** | Scrapes news → summarizes with Claude → texts each subscriber | GitHub Actions (daily cron) |
| **Reply handler** | Answers inbound texts, updates topics, handles STOP/START | Twilio Function |
| **Sign-up + site** | Landing page + opt-in form that records consent | Vercel |

All three share one **Postgres database** (`subscribers` + `consent_log` tables).

---

## 0. Database (Supabase)

**Create the tables:** open your Supabase project → **SQL Editor** → **New query**
→ paste all of [`schema.sql`](schema.sql) → **Run**. You'll get `subscribers` and
`consent_log` (check the **Table Editor** to confirm).

**Get your connection strings** (Settings → Database → Connection string → URI):
- **Serverless functions** (Twilio Function, Vercel API) → use the **Transaction
  pooler**, port `6543`. The code sets `prepare: false` for this pooler.
  ```
  postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
  ```
- **GitHub Actions** morning job (a once-a-day batch) → use the **Session pooler**
  / direct connection, port `5432`.

These are your `DATABASE_URL` values. Keep them secret — never commit them.

**Seed yourself as the first subscriber** (Supabase SQL Editor — use your real number):
```sql
INSERT INTO subscribers (phone, topics, status, consent_at, consent_text)
VALUES ('+1XXXXXXXXXX', '{ai,politics,business}', 'active', now(), 'Owner self-enrolled')
ON CONFLICT (phone) DO NOTHING;
```

---

## 1. Morning briefing → GitHub Actions

The workflow is at [`.github/workflows/briefing.yml`](.github/workflows/briefing.yml).
It runs `python main.py` daily at **12:00 UTC** (≈ 7am US Central — edit the cron to change).

**Add repo secrets** in GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**:

- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`  (your toll-free number, E.164, e.g. `+18XXXXXXXXX`)
- `DATABASE_URL`

Optional **Variables** (not secret): `OPENAI_MODEL` (defaults to `gpt-4o-mini`),
`LLM_PROVIDER` (defaults to `openai`).

> **Switching to Claude later:** set Variable `LLM_PROVIDER=anthropic` and add the
> secret `ANTHROPIC_API_KEY`. No code change needed.

**Test it now:** GitHub → **Actions** tab → *Morning Briefing* → **Run workflow**.
Watch the logs; you should get a text (once your number is verified — see §5).

---

## 2. Reply handler → Twilio Function

Code: [`twilio-function/functions/sms.js`](twilio-function/functions/sms.js).

**Option A — Twilio Console (no CLI):**
1. Console → **Functions & Assets → Services → Create Service** (name it `newsbot`).
2. **Dependencies** tab → add `openai` and `postgres`.
3. **Environment Variables** tab → add `OPENAI_API_KEY` and `DATABASE_URL`
   (optionally `OPENAI_MODEL`; to use Claude instead, set `LLM_PROVIDER=anthropic`
   and add `ANTHROPIC_API_KEY`).
4. Add a **Function**, path `/sms`, set it to **Protected** or **Public**
   (Public is fine to start), paste in `sms.js`, and **Deploy**.
5. Copy the function URL (e.g. `https://newsbot-1234.twil.io/sms`).

**Option B — Twilio CLI (from `twilio-function/`):**
```bash
cd twilio-function
cp .env.example .env        # fill in your real values
npm install
npx twilio serverless:deploy
```

---

## 3. Point your number at the reply handler

Twilio Console → **Phone Numbers → your number → Messaging →
"A message comes in"** → **Function** (or Webhook) → select your `/sms` function →
**Save**. This replaces the demo webhook.

Leave **Advanced Opt-Out ON** (Messaging Service settings) so Twilio handles
STOP/HELP for carrier compliance. The function also logs those events to keep the
database in sync.

---

## 4. Sign-up site → Vercel

The site lives in [`website/`](website/) with the opt-in API at
[`website/api/subscribe.js`](website/api/subscribe.js).

1. Vercel → **Add New → Project** → import `SMalshe/NewsBot`.
2. **Root Directory → `website`** (important — deploys the site + API, not the Python).
3. **Environment Variables** → add `DATABASE_URL`.
4. **Deploy.** Your sign-up form now writes subscribers + consent records.

(CLI alternative: `cd website && npx vercel --prod`, then add the env var with
`vercel env add DATABASE_URL`.)

---

## 5. Twilio toll-free verification

Submit the verification with:
- **Website:** your Vercel URL
- **Opt-in:** "Users enter their number and check a consent box on our website;
  consent is recorded with timestamp and IP in a `consent_log` table." (true now!)
- **Sample messages:** copy from the site's phone mockup
- **Opt-out:** STOP / HELP supported

Until verification is approved, your number can't send SMS — the morning job will
error on send. That's expected.

---

## Where consent is stored (proof for carriers)

- **`subscribers.consent_at` / `consent_text`** — each user's latest consent.
- **`consent_log`** — an immutable, append-only record of *every* opt-in/opt-out,
  with method (`web_form` / `sms_keyword`), the exact agreed language, plus IP and
  user-agent for web sign-ups. Query it anytime:
  ```sql
  SELECT * FROM consent_log WHERE phone = '+1XXXXXXXXXX' ORDER BY created_at;
  ```

---

## Local test of the morning job
```bash
pip install -r requirements.txt
export DATABASE_URL=... OPENAI_API_KEY=... TWILIO_ACCOUNT_SID=... \
       TWILIO_AUTH_TOKEN=... TWILIO_FROM_NUMBER=...
python main.py
```
