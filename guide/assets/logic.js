/* Faithful JavaScript ports of the backend's pure logic, so the widgets show
   REAL behaviour, not a cartoon. Each function names the Python source it mirrors.
   guide/tools/check_ports.py runs the Python originals and these ports side by
   side to prove they agree. */
(function (root) {
  "use strict";

  /* ── src/order_ids.py ── */
  const ORD = () => /(?<![A-Za-z0-9])ORD[-\s]?(\d{4})(?!\d)/gi;
  function normalize(raw) {
    const m = raw.trim().match(/^(?<![A-Za-z0-9])ORD[-\s]?(\d{4})$/i);
    return m ? "ORD-" + m[1] : null;
  }
  function findOrderIds(text) {
    const out = [];
    for (const m of text.matchAll(ORD())) { const id = "ORD-" + m[1]; if (!out.includes(id)) out.push(id); }
    return out;
  }
  /* agent.handle(): Extraction validator + grounding */
  function normalizeProposal(list) {
    const out = [];
    for (const raw of list) { const id = normalize(raw); if (id && !out.includes(id)) out.push(id); }
    return out;
  }
  function ground(proposed, text) {
    const written = findOrderIds(text);
    return proposed.filter((id) => written.includes(id));
  }

  /* ── src/policy_engine.py ── */
  const RETURN_WINDOW_DAYS = 14;
  const KNOWN_STATUSES = ["processing", "shipped", "delivered"];
  const dayNum = (iso) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d) / 86400000; };
  function decide(intent, order, productState, today) {
    const D = (rule, action, sr, sources, why) => ({ rule, action, sr, sources, why });
    if (!KNOWN_STATUSES.includes(order.status))
      return D("R0", "escalate", "agent_handoff", ["POL-07"], "Status '" + order.status + "' is not covered by the policy, so a human takes it.");
    if (intent === "order_status" || intent === "delivery_delay") {
      if (order.delivered_at == null && dayNum(today) > dayNum(order.estimated_delivery))
        return D("R1", "reply", "shipping_inquiry", ["POL-03", "POL-02"], "The estimate has passed and it has not arrived: open a shipping inquiry.");
      return D("R2", "reply", null, ["POL-02"], "Show the status and the estimated date, as an estimate only.");
    }
    if (intent === "cancel") {
      if (order.status === "processing") return D("R3", "reply", "cancellation", ["POL-04"], "Processing: a cancellation request can be opened.");
      if (order.status === "shipped") return D("R4", "reply", null, ["POL-04"], "Already shipped: cannot cancel, a return can be considered after delivery.");
      if (order.status === "delivered") return D("R5", "reply", null, ["POL-04", "POL-05"], "Already delivered: cancelling makes no sense, point to the return route.");
    }
    if (intent === "return") {
      if (order.delivered_at == null) return D("R6", "reply", null, ["POL-05"], "Not delivered yet: a return is possible only after delivery.");
      if (!(dayNum(today) <= dayNum(order.delivered_at) + RETURN_WINDOW_DAYS))
        return D("R7", "escalate", "agent_handoff", ["POL-05"], "The 14 day window has passed: a human decides, with no promise of approval.");
      if (productState === "opened") return D("R8", "escalate", "agent_handoff", ["POL-05"], "Product was opened: outside the return terms, a human decides.");
      if (productState === "unknown") return D("R9", "clarify", null, ["POL-05", "POL-07"], "Product state unknown: ask before deciding.");
      return D("R10", "reply", "return", ["POL-05"], "Inside the window and unopened: open a return request.");
    }
    if (intent === "damaged_item") return D("R11", "escalate", "agent_handoff", ["POL-06"], "A damaged item always goes to a human, with no promise of refund or replacement.");
    return D("R12", "escalate", "agent_handoff", ["POL-07"], "No policy covers this: a human takes it.");
  }

  /* ── src/order_service.py ── */
  const ORDERS = [
    { order_id: "ORD-1001", customer_id: "C-101", status: "processing", estimated_delivery: "2026-09-25", delivered_at: null },
    { order_id: "ORD-1002", customer_id: "C-101", status: "shipped", estimated_delivery: "2026-09-20", delivered_at: null },
    { order_id: "ORD-1003", customer_id: "C-101", status: "delivered", estimated_delivery: "2026-09-12", delivered_at: "2026-09-12" },
    { order_id: "ORD-1004", customer_id: "C-101", status: "delivered", estimated_delivery: "2026-09-01", delivered_at: "2026-09-01" },
    { order_id: "ORD-1005", customer_id: "C-202", status: "shipped", estimated_delivery: "2026-09-24", delivered_at: null },
    { order_id: "ORD-1006", customer_id: "C-101", status: "shipped", estimated_delivery: "2026-09-24", delivered_at: null },
  ];
  function getOrder(orderId, customerId, opts) {
    opts = opts || {};
    const orders = opts.orders || ORDERS;
    if (opts.outage) return { error: "OrderServiceUnavailable" };
    for (const o of orders) {
      if (o.order_id === orderId) {
        if (o.customer_id !== customerId) return { order: null };
        if (!/^ORD-\d{4}$/.test(o.order_id) || !o.status || !o.estimated_delivery || (o.status === "delivered" && !o.delivered_at)) return { error: "OrderDataInvalid" };
        return { order: o };
      }
    }
    return { order: null };
  }

  /* ── src/reply_guard.py ── */
  const HE_MONTHS = { "ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5, "יוני": 6, "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12 };
  const EN_MONTHS = {};
  [["january", "jan"], ["february", "feb"], ["march", "mar"], ["april", "apr"], ["may"], ["june", "jun"], ["july", "jul"], ["august", "aug"], ["september", "sept", "sep"], ["october", "oct"], ["november", "nov"], ["december", "dec"]]
    .forEach((names, i) => names.forEach((n) => (EN_MONTHS[n] = i + 1)));
  const EN_ALT = Object.keys(EN_MONTHS).sort((a, b) => b.length - a.length).join("|");
  const HE_ALT = Object.keys(HE_MONTHS).join("|");
  const COMMITMENT = new RegExp(
    "בוטל|אושר|אישרנו|פיצוי|נפצה|נחזיר\\s+לך|מובטח|נבטיח|מבטיחים" +
    "|תקבל(?:י|ו)?\\s+(?:\\S+\\s+)?(?:החזר|החלפה|זיכוי)" +
    "|\\bcancell?ed\\b|\\bapproved\\b|\\bcompensat\\w*|\\brefund(?:ed|s)?\\b|\\bguarantee[ds]?\\b" +
    "|\\bwill\\s+(?:receive|get)\\s+(?:a\\s+|your\\s+)?(?:refund|replacement|compensation)", "i");
  const RELATIVE = new RegExp(
    "מחרתיים|מחר|בימים הקרובים|בשבוע הבא|תוך\\s+\\d+\\s+(?:ימים|ימי עסקים|שעות)" +
    "|\\btomorrow\\b|\\bnext week\\b|\\bin the (?:coming|next)(?: few)? days\\b|\\bwithin\\s+\\d+\\s+(?:business\\s+)?(?:days|hours)\\b", "i");
  const CURRENCY = /₪|ש"ח|ש״ח|\bNIS\b|\bILS\b|€|\$\s?\d|\d\s?\$|\bshekels?\b/i;
  const INTERNAL = /\bPOL-\d{2}\b|agent_handoff|shipping_inquiry|internal_reason|decision_context/;
  const SR_ID = /(?<![A-Za-z0-9])SR-\d+(?!\d)/g;
  const ISO_DATE = /(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)/g;
  const NUM_DATE = /(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{2,4})(?!\d)/g;
  const HE_WORD_DATE = new RegExp("(?<!\\d)(\\d{1,2})\\s+ב?(" + HE_ALT + ")(?:\\s+(\\d{4}))?", "g");
  const EN_MONTH_FIRST = new RegExp("\\b(" + EN_ALT + ")\\.?\\s+(\\d{1,2})(?:st|nd|rd|th)?\\b(?:,?\\s+(\\d{4}))?", "gi");
  const EN_DAY_FIRST = new RegExp("(?<!\\d)(\\d{1,2})(?:st|nd|rd|th)?\\s+(?:of\\s+)?(" + EN_ALT + ")\\b\\.?(?:,?\\s+(\\d{4}))?", "gi");
  const yr = (raw) => (!raw ? null : raw.length === 2 ? 2000 + Number(raw) : Number(raw));

  function mentionedDates(text) {
    const f = [];
    for (const m of text.matchAll(ISO_DATE)) f.push([m[0], Number(m[1]), Number(m[2]), Number(m[3])]);
    for (const m of text.matchAll(NUM_DATE)) f.push([m[0], yr(m[3]), Number(m[2]), Number(m[1])]);
    for (const m of text.matchAll(HE_WORD_DATE)) f.push([m[0], yr(m[3]), HE_MONTHS[m[2]], Number(m[1])]);
    for (const m of text.matchAll(EN_MONTH_FIRST)) f.push([m[0], yr(m[3]), EN_MONTHS[m[1].toLowerCase()], Number(m[2])]);
    for (const m of text.matchAll(EN_DAY_FIRST)) f.push([m[0], yr(m[3]), EN_MONTHS[m[2].toLowerCase()], Number(m[1])]);
    return f;
  }
  function parseDate(raw) {
    const p = mentionedDates(raw);
    if (!p.length) return null;
    const [, y, m, d] = p[0];
    if (!y) return null;
    const dt = new Date(Date.UTC(y, m - 1, d));
    return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d ? { year: y, month: m, day: d } : null;
  }
  /* returns [{kind, detail}] ; empty = passed */
  function guardCheck(reply, orderId, allowedDates, srId) {
    const v = [];
    const leaked = findOrderIds(reply).filter((o) => o !== orderId);
    if (leaked.length) v.push({ kind: "order", detail: "Mentions an order that is not this one: " + leaked.sort().join(", ") });
    const allowed = allowedDates.map(parseDate).filter(Boolean);
    for (const [raw, y, m, d] of mentionedDates(reply)) {
      if (!allowed.some((a) => a.month === m && a.day === d && (y == null || a.year === y)))
        v.push({ kind: "date", detail: "A date that is not in the facts package: " + raw });
    }
    [[COMMITMENT, "commitment", "Forbidden promise word"], [RELATIVE, "relative", "Relative deadline (a promise of timing)"],
     [CURRENCY, "currency", "Amount or currency"], [INTERNAL, "internal", "Internal code or term"]].forEach(([rx, kind, label]) => {
      const hit = reply.match(rx);
      if (hit) v.push({ kind, detail: label + ": " + hit[0] });
    });
    const mentioned = new Set(reply.match(SR_ID) || []);
    const foreign = [...mentioned].filter((s) => s !== srId);
    if (foreign.length) v.push({ kind: "sr_foreign", detail: "Mentions a request number that is not ours: " + foreign.sort().join(", ") });
    if (srId && !mentioned.has(srId)) v.push({ kind: "sr_missing", detail: "The service request number is missing from the reply" });
    return v;
  }
  const FALLBACK = {
    he: {
      reply_with_sr: "הבקשה שלך נקלטה במערכת, מספר בקשה {sr_id}. הבקשה בבדיקה ואינה מהווה אישור סופי לתוצאה.",
      reply_no_sr: "בדקתי את הפנייה שלך במערכת. לצערי אין לי מידע נוסף מעבר לכך במסגרת המדיניות הקיימת.",
      clarify: "כדי להמשיך בבירור הפנייה אני צריך/ה פרט נוסף ממך — תוכל/י לפרט?",
      escalate_with_sr: "העברתי את הפנייה שלך לנציג אנושי, מספר פנייה {sr_id}. נציג יחזור אליך; אין באפשרותי להבטיח את תוצאת הטיפול.",
      escalate_no_sr: "העברתי את הפנייה שלך לנציג אנושי לבירור נוסף. נציג יחזור אליך; אין באפשרותי להבטיח את תוצאת הטיפול.",
    },
    en: {
      reply_with_sr: "Your request has been received, request number {sr_id}. It is under review and is not a final confirmation of the outcome.",
      reply_no_sr: "I checked your request in our system, but I have no further information to share under the current policy.",
      clarify: "To continue with your request I need one more detail from you — could you provide it?",
      escalate_with_sr: "I've forwarded your request to a human agent, reference number {sr_id}. An agent will get back to you; I can't promise the outcome.",
      escalate_no_sr: "I've forwarded your request to a human agent for further review. An agent will get back to you; I can't promise the outcome.",
    },
  };
  function fallbackReply(action, srId, lang) {
    const t = FALLBACK[lang] || FALLBACK.he;
    if (action === "clarify") return t.clarify;
    const tpl = t[action + "_" + (srId ? "with_sr" : "no_sr")];
    return srId ? tpl.replace("{sr_id}", srId) : tpl;
  }

  /* ── src/llm.py : run_structured() ── */
  /* modes: ok | schema_once | schema_always | transient_once | transient_always | permanent */
  function simulateChain(providers) {
    const log = []; let calls = 0;
    for (const p of providers) {
      if (!p.hasKey && p.name !== "local") { log.push({ t: "skip", text: p.name + ": skipped, no API key" }); continue; }
      let repair = false;
      for (const attempt of [1, 2]) {
        calls++;
        const tag = p.name + " attempt " + attempt + (repair ? " (repair prompt)" : "");
        let outcome = "ok";
        if (p.mode === "schema_always") outcome = "schema";
        else if (p.mode === "schema_once") outcome = attempt === 1 ? "schema" : "ok";
        else if (p.mode === "transient_always") outcome = "transient";
        else if (p.mode === "transient_once") outcome = attempt === 1 ? "transient" : "ok";
        else if (p.mode === "permanent") outcome = "permanent";
        if (outcome === "ok") { log.push({ t: "ok", text: tag + ": ok" }); return { log, calls, winner: p.name }; }
        if (outcome === "schema") { log.push({ t: "warn", text: tag + ": schema error" }); repair = true; continue; }
        if (outcome === "transient") {
          log.push({ t: "warn", text: tag + ": transport error (timeout, 429 or 5xx)" });
          if (attempt === 1) { log.push({ t: "info", text: "wait 1 second, retry once" }); continue; }
          break;
        }
        log.push({ t: "bad", text: tag + ": permanent error (401 or 400), no retry" });
        break;
      }
      log.push({ t: "info", text: p.name + " is out, moving to the next provider" });
    }
    log.push({ t: "bad", text: "AllProvidersFailed" });
    return { log, calls, winner: null };
  }

  /* ── src/llm.py : config ── */
  const KNOWN = ["local", "grok", "gemini"];
  function resolveConfig(env) {
    const raw = env.PROVIDERS || "gemini";
    const names = raw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
    const unknown = names.filter((n) => !KNOWN.includes(n));
    if (unknown.length) return { error: "unknown provider(s) in PROVIDERS: " + unknown.join(", ") + " (supported: " + KNOWN.join(", ") + ")" };
    const cfg = (n) => n === "local" ? { model: env.LOCAL_MODEL || "local-model", key: "not-needed" }
      : n === "grok" ? { model: env.XAI_MODEL || "grok-4-fast", key: env.XAI_API_KEY || "" }
      : { model: env.GEMINI_MODEL || "gemini-3.1-flash-lite", key: env.GEMINI_API_KEY || "" };
    const usable = [], skipped = [];
    names.forEach((n) => { const c = cfg(n); if (n !== "local" && !c.key) skipped.push(n); else usable.push({ name: n, model: c.model }); });
    if (!usable.length) return { error: "no usable model provider: set PROVIDERS (e.g. gemini) and the matching API key (GEMINI_API_KEY / XAI_API_KEY) in .env", skipped };
    return { usable, skipped };
  }

  /* ── src/agent.py : failure paths ── */
  const MSG = {
    he: {
      extraction_failed_forwarded: "מצטערים, לא ניתן להשלים את הבקשה כרגע. הפנייה הועברה לבדיקה.",
      outage_forwarded: "לא ניתן לבדוק את ההזמנה כרגע עקב תקלה טכנית. הפנייה הועברה לבירור נוסף.",
      data_invalid_forwarded: "לא ניתן להשלים את בדיקת ההזמנה באופן אוטומטי כרגע. הפנייה הועברה לנציג לבירור.",
      tech_failure: "לא ניתן להשלים את הבקשה כרגע עקב תקלה טכנית. אנא נסו שוב בעוד מספר דקות.",
    },
    en: {
      extraction_failed_forwarded: "Sorry, we can't complete your request right now. It has been forwarded for review.",
      outage_forwarded: "We can't check the order right now due to a technical issue. Your request has been forwarded for follow-up.",
      data_invalid_forwarded: "We can't complete the automatic check of this order right now. Your request has been forwarded to an agent.",
      tech_failure: "We can't complete your request right now due to a technical issue. Please try again in a few minutes.",
    },
  };
  /* what: providers | outage | baddata | srwrite ; handoffFails: bool */
  function failureOutcome(what, handoffFails, lang) {
    const rows = [];
    if (what === "srwrite") {
      return { action: "escalate", reply: MSG[lang].tech_failure, rows: [], staff: "Writing the service request failed, so none was created. No number is quoted.", handoff: "none" };
    }
    const forwarded = { providers: "extraction_failed_forwarded", outage: "outage_forwarded", baddata: "data_invalid_forwarded" }[what];
    const reason = { providers: "All model providers failed at extraction", outage: "The order service is unavailable", baddata: "The order record is malformed" }[what];
    if (!handoffFails) {
      return { action: "escalate", reply: MSG[lang][forwarded], rows: [{ id: "SR-000007", type: "agent_handoff", order: what === "providers" ? null : "ORD-1001" }], staff: reason + ". A handoff record was written for staff.", handoff: "written" };
    }
    return { action: "escalate", reply: MSG[lang].tech_failure, rows: [], staff: reason + ". The handoff write also failed, so the reply does not claim anything was forwarded.", handoff: "failed" };
  }

  const api = { normalize, findOrderIds, normalizeProposal, ground, decide, ORDERS, getOrder, mentionedDates, parseDate, guardCheck, fallbackReply, FALLBACK, simulateChain, resolveConfig, failureOutcome, dayNum, KNOWN_STATUSES };
  root.GuideLogic = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
