# Running the same setup on Supabase

Both Neon and Supabase are plain Postgres, so the **schema and the Python side are
identical** — only the JavaScript serverless driver differs (the
`@neondatabase/serverless` package is Neon-specific).

## 1. Create the tables
Supabase Dashboard → **SQL Editor** → paste and run [`schema.sql`](schema.sql).
That creates `subscribers` and `consent_log`, same as Neon.

## 2. Get the connection string
Supabase Dashboard → **Project Settings → Database → Connection string → URI**.
Use the **Transaction pooler** (port `6543`) URL for serverless functions:
```
postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```
This becomes your `DATABASE_URL`.

## 3. Python side — no change
`db.py` uses `psycopg2`, which works with Supabase as-is. Just set `DATABASE_URL`
to the Supabase URI in your GitHub Actions secrets.

## 4. JavaScript side — swap the driver
The Neon HTTP driver only talks to Neon. For Supabase, use the portable
[`postgres`](https://github.com/porsager/postgres) package instead.

**Twilio Function** (`twilio-function/package.json` dependency) and
**Vercel API** (`website/package.json` dependency): replace
`@neondatabase/serverless` with `postgres`.

Then change the connection setup at the top of each file:

```js
// BEFORE (Neon):
const { neon } = require("@neondatabase/serverless");
const sql = neon(process.env.DATABASE_URL);

// AFTER (Supabase / any Postgres):
const postgres = require("postgres");
const sql = postgres(process.env.DATABASE_URL, { ssl: "require" });
```

The query syntax is the **same tagged-template style** (`` sql`SELECT ...` ``), so
the rest of `sms.js` and `subscribe.js` works unchanged.

> Tip: if you want one codebase that runs on **either** Neon or Supabase without
> edits, standardize on the `postgres` package everywhere — it works with both.
> (I used the Neon driver by default since the DB was provisioned on Neon.)

## 5. Optional — Row Level Security
Supabase enables RLS prompts by default. Since only your **server-side** functions
(using the service connection string) touch these tables — never the browser —
you can leave RLS off, or enable it with no public policies so only the service
role has access. Do **not** expose these tables through Supabase's public REST/anon
API.

## Which should you use?
- **Neon** — already provisioned here; serverless HTTP driver is a great fit for
  Twilio Functions; generous free tier.
- **Supabase** — also great, gives you a dashboard/table editor, auth, and storage
  if you later grow the product. You already know it from the Leafy project.

You can't easily run both as the live backend at once (they'd hold separate
subscriber lists). Pick one for `DATABASE_URL`; keep the other as a backup/option.
