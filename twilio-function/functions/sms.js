// sms.js — Twilio Function. Triggered when someone texts your number.
// Configure your number's "A message comes in" webhook to point here.
//
// Required Environment Variables (set in the Twilio Service settings):
//   ANTHROPIC_API_KEY   - your Anthropic key
//   DATABASE_URL        - Supabase connection string (Transaction pooler, port 6543)
//   ANTHROPIC_MODEL     - optional, defaults to claude-haiku-4-5-20251001
//
// Dependencies (add in the Service "Dependencies" tab):
//   @anthropic-ai/sdk
//   postgres
//
// Design notes:
//  - STOP / HELP / START are intercepted by Twilio's Advanced Opt-Out BEFORE
//    this runs (leave it ON for compliance); we also handle them here as a
//    fallback so the database stays in sync.
//  - Exactly ONE Claude call per message (decide + reply in a single request)
//    to stay well under Twilio's 10-second function timeout.
//  - `prepare: false` is required for Supabase's transaction pooler (PgBouncer).

const Anthropic = require("@anthropic-ai/sdk");
const postgres = require("postgres");

const STOP_WORDS = ["stop", "stopall", "unsubscribe", "cancel", "end", "quit"];
const START_WORDS = ["start", "unstop", "yes"];

exports.handler = async function (context, event, callback) {
  const twiml = new Twilio.twiml.MessagingResponse();
  const from = event.From;
  const body = (event.Body || "").trim();
  const lower = body.toLowerCase();

  const sql = postgres(context.DATABASE_URL, { ssl: "require", prepare: false });
  const model = context.ANTHROPIC_MODEL || "claude-haiku-4-5-20251001";
  const anthropic = new Anthropic({ apiKey: context.ANTHROPIC_API_KEY });

  let reply;
  try {
    // --- Opt-out / opt-in fallback (no LLM needed) ------------------------
    if (STOP_WORDS.includes(lower)) {
      await sql`UPDATE subscribers SET status = 'stopped' WHERE phone = ${from}`;
      await sql`INSERT INTO consent_log (phone, event, method, consent_text)
                VALUES (${from}, 'opt_out', 'sms_keyword', ${"User texted: " + body})`;
      reply = "You've been unsubscribed and won't get more briefings. Reply START to resubscribe.";
    } else if (START_WORDS.includes(lower)) {
      await sql`UPDATE subscribers SET status = 'active' WHERE phone = ${from}`;
      await sql`INSERT INTO consent_log (phone, event, method, consent_text)
                VALUES (${from}, 'opt_in', 'sms_keyword', ${"User texted: " + body})`;
      reply = "You're resubscribed to Daily Brief. Reply STOP anytime to cancel.";
    } else {
      // --- Look up the subscriber ----------------------------------------
      const rows = await sql`SELECT phone, topics, status FROM subscribers WHERE phone = ${from}`;
      if (rows.length === 0) {
        reply = "You're not subscribed to Daily Brief. Sign up on our website to start receiving briefings.";
      } else {
        const sub = rows[0];

        // --- One Claude call: decide intent AND produce the reply --------
        const out = await anthropic.messages.create({
          model,
          max_tokens: 350,
          system:
            "You are the SMS assistant for a personal news service called Daily Brief. " +
            `The subscriber's current topics are: ${JSON.stringify(sub.topics)}. ` +
            "Decide whether their message asks to CHANGE their news topics, or is a general message/question. " +
            "Reply with ONLY minified JSON, no other text, shaped exactly like: " +
            '{"action":"update_topics"|"reply","topics":["lowercase","keywords"],"reply":"short casual SMS reply, 1-3 sentences, no formatting"}. ' +
            'Use "update_topics" only if they want to add/remove/replace topics; then "topics" MUST be the FULL updated list and "reply" confirms it. ' +
            'Otherwise use "reply" to answer helpfully and leave "topics" as the unchanged list.',
          messages: [{ role: "user", content: body }],
        });

        let action = "reply";
        let topics = sub.topics;
        reply = "";
        const match = (out.content[0].text || "").match(/\{[\s\S]*\}/);
        if (match) {
          try {
            const parsed = JSON.parse(match[0]);
            if (parsed.action) action = parsed.action;
            if (Array.isArray(parsed.topics) && parsed.topics.length) {
              topics = parsed.topics.map((t) => String(t).toLowerCase().trim());
            }
            if (typeof parsed.reply === "string") reply = parsed.reply.trim();
          } catch (e) {
            /* fall through with defaults */
          }
        }
        if (!reply) reply = "Got it!";

        if (action === "update_topics") {
          await sql`UPDATE subscribers SET topics = ${sql.array(topics)} WHERE phone = ${from}`;
        }
      }
    }
  } catch (err) {
    console.error(err);
    reply = "Sorry, something went wrong on my end. Try again in a bit.";
  } finally {
    await sql.end({ timeout: 5 }).catch(() => {});
  }

  twiml.message(reply);
  return callback(null, twiml);
};
