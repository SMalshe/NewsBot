# Database: Supabase

This project uses **Supabase** (Postgres) as its backend. The code is already
wired for it — this doc explains the setup and the few Supabase-specific details.

## 1. Create the tables
Supabase Dashboard → **SQL Editor** → **New query** → paste all of
[`schema.sql`](schema.sql) → **Run**. That creates `subscribers` and `consent_log`.

## 2. Connection strings
Settings → **Database → Connection string → URI**. There are two; use the right
one for each consumer:

| Consumer | Pooler | Port |
|----------|--------|------|
| Twilio Function + Vercel API (serverless) | **Transaction pooler** | `6543` |
| GitHub Actions morning job (batch) | **Session pooler** / direct | `5432` |

```
postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

## 3. Driver (already configured)
The serverless functions use the [`postgres`](https://github.com/porsager/postgres)
library, which works with Supabase via a standard connection string:

```js
const postgres = require("postgres");
const sql = postgres(process.env.DATABASE_URL, { ssl: "require", prepare: false });
```

> **`prepare: false` matters.** Supabase's transaction pooler (PgBouncer, port
> 6543) does not support prepared statements. This flag is already set in
> `twilio-function/functions/sms.js` and `website/api/subscribe.js`.

The Python side (`db.py`) uses `psycopg2`, which works with Supabase unchanged —
just point `DATABASE_URL` at the port-`5432` connection for the batch job.

## 4. Row Level Security
Only server-side code (with the connection string) touches these tables — never
the browser. Leave RLS off, or enable it with no public policies so only the
service role has access. Do **not** expose these tables through Supabase's public
REST/anon API.

## Switching back to Neon (if ever needed)
A Neon project `news-bot` was provisioned earlier as a fallback. To use it
instead, swap the `postgres` dependency for `@neondatabase/serverless` and change
the two connection lines to `const sql = neon(process.env.DATABASE_URL)`. The
tagged-template query syntax is the same either way.
