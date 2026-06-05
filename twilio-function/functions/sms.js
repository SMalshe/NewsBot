// sms.js — Twilio Function. Triggered when someone texts your number.
// Configure your number's "A message comes in" webhook to point here.
//
// Required Environment Variables (set in the Twilio Service settings):
//   ANTHROPIC_API_KEY   - your Anthropic key
//   DATABASE_URL        - the Neon Postgres connection string
//   ANTHROPIC_MODEL     - optional, defaults to claude-haiku-4-5-20251001
//
// Dependencies (add in the Service "Dependencies" tab):
//   @anthropic-ai/sdk
//   @neondatabase/serverless
//
// Note: STOP / HELP / START are intercepted by Twilio's Advanced Opt-Out
// BEFORE this function runs (leave it ON for carrier compliance). We also
// handle them here as a fallback so the database stays in sync if it's off.

const Anthropic = require("@anthropic-ai/sdk");
const { neon } = require("@neondatabase/serverless");

const STOP_WORDS = ["stop", "stopall", "unsubscribe", "cancel", "end", "quit"];
const START_WORDS = ["start", "unstop", "yes"];

exports.handler = async function (context, event, callback) {
  const twiml = new Twilio.twiml.MessagingResponse();
  const from = event.From;
  const body = (event.Body || "").trim();
  const lower = body.toLowerCase();

  const sql = neon(context.DATABASE_URL);
  const model = context.ANTHROPIC_MODEL || "claude-haiku-4-5-20251001";
  const anthropic = new Anthropic({ apiKey: context.ANTHROPIC_API_KEY });

  try {
    // --- Opt-out / opt-in fallback handling -------------------------------
    if (STOP_WORDS.includes(lower)) {
      await sql`UPDATE subscribers SET status = 'stopped' WHERE phone = ${from}`;
      await sql`INSERT INTO consent_log (phone, event, method, consent_text)
                VALUES (${from}, 'opt_out', 'sms_keyword', ${"User texted: " + body})`;
      twiml.message("You've been unsubscribed and won't get more briefings. Reply START to resubscribe.");
      return callback(null, twiml);
    }
    if (START_WORDS.includes(lower)) {
      await sql`UPDATE subscribers SET status = 'active' WHERE phone = ${from}`;
      await sql`INSERT INTO consent_log (phone, event, method, consent_text)
                VALUES (${from}, 'opt_in', 'sms_keyword', ${"User texted: " + body})`;
      twiml.message("You're resubscribed to Daily Brief. Reply STOP anytime to cancel.");
      return callback(null, twiml);
    }

    // --- Look up the subscriber ------------------------------------------
    const rows = await sql`SELECT phone, topics, status FROM subscribers WHERE phone = ${from}`;
    if (rows.length === 0) {
      twiml.message("You're not subscribed to Daily Brief. Sign up on our website to start receiving briefings.");
      return callback(null, twiml);
    }
    const sub = rows[0];

    // --- Is this a preference command or a question? ----------------------
    const cls = await anthropic.messages.create({
      model,
      max_tokens: 5,
      system:
        "You classify a text message sent to a personal news bot. Reply with exactly one word: " +
        "'command' if the user is asking to change which news topics they receive, otherwise 'question'.",
      messages: [{ role: "user", content: body }],
    });
    const kind = (cls.content[0].text || "").toLowerCase();

    if (kind.includes("command")) {
      // Ask Claude for the full updated topic list as JSON.
      const ext = await anthropic.messages.create({
        model,
        max_tokens: 200,
        system:
          "You update a news subscriber's topic list. Return ONLY valid JSON of the form " +
          '{"topics":["topic1","topic2"]} containing the FULL updated list of lowercase topic keywords. No other text.',
        messages: [
          {
            role: "user",
            content: `Current topics: ${JSON.stringify(sub.topics)}\nUser request: ${body}`,
          },
        ],
      });
      let topics = sub.topics;
      const match = (ext.content[0].text || "").match(/\{[\s\S]*\}/);
      if (match) {
        try {
          const parsed = JSON.parse(match[0]);
          if (Array.isArray(parsed.topics) && parsed.topics.length) {
            topics = parsed.topics.map((t) => String(t).toLowerCase().trim());
          }
        } catch (e) {
          /* fall back to existing topics */
        }
      }
      await sql`UPDATE subscribers SET topics = ${topics} WHERE phone = ${from}`;
      twiml.message(`Done! Your topics are now: ${topics.join(", ")}. You'll see this in tomorrow's brief.`);
      return callback(null, twiml);
    }

    // --- Otherwise: answer their question casually ------------------------
    const ans = await anthropic.messages.create({
      model,
      max_tokens: 300,
      system:
        "You are a friendly, knowledgeable news companion replying by SMS. " +
        "Keep replies short and casual — 1 to 3 sentences, no bullet points or formatting.",
      messages: [{ role: "user", content: body }],
    });
    twiml.message((ans.content[0].text || "").trim());
    return callback(null, twiml);
  } catch (err) {
    console.error(err);
    twiml.message("Sorry, something went wrong on my end. Try again in a bit.");
    return callback(null, twiml);
  }
};
