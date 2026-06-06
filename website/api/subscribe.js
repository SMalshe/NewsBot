// api/subscribe.js — Vercel Serverless Function for the sign-up form.
// Writes a new subscriber to the Neon database WITH a record of consent.
//
// Required Vercel Environment Variable:
//   DATABASE_URL  - the Neon Postgres connection string
//
// Keeping a consent record (consent_at + consent_text) matters: SMS carriers
// can ask you to prove each person opted in.
const postgres = require("postgres");

// Module-scope connection is reused across warm invocations.
// `prepare: false` is required for Supabase's transaction pooler (PgBouncer).
const sql = postgres(process.env.DATABASE_URL, { ssl: "require", prepare: false });

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { phone, consent } = req.body || {};

  if (!consent) {
    return res.status(400).json({ error: "You must agree to receive text messages to sign up." });
  }

  // Normalize to E.164-ish: strip everything but digits and a leading +.
  let normalized = String(phone || "").replace(/[^\d+]/g, "");
  if (normalized && !normalized.startsWith("+")) {
    // Assume US if no country code was given.
    normalized = normalized.length === 10 ? "+1" + normalized : "+" + normalized;
  }
  if (!/^\+\d{11,15}$/.test(normalized)) {
    return res.status(400).json({ error: "Please enter a valid phone number, including area code." });
  }

  const consentText =
    "Web sign-up: user checked the box agreeing to receive a recurring daily news briefing and reply messages by SMS from Daily Brief.";
  const ip =
    (req.headers["x-forwarded-for"] || "").split(",")[0].trim() ||
    req.socket?.remoteAddress ||
    null;
  const userAgent = req.headers["user-agent"] || null;

  try {
    await sql`
      INSERT INTO subscribers (phone, status, consent_at, consent_text)
      VALUES (${normalized}, 'active', now(), ${consentText})
      ON CONFLICT (phone)
      DO UPDATE SET status = 'active', consent_at = now(), consent_text = ${consentText}
    `;
    // Append an immutable consent record (audit trail / proof of consent).
    await sql`
      INSERT INTO consent_log (phone, event, method, consent_text, ip, user_agent)
      VALUES (${normalized}, 'opt_in', 'web_form', ${consentText}, ${ip}, ${userAgent})
    `;
    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Something went wrong. Please try again later." });
  }
};
