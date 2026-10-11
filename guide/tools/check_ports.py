"""Proves the browser widgets behave like the real backend.

Runs the Python originals (src/order_ids, policy_engine, reply_guard) and the
JavaScript ports (guide/assets/logic.js, through node) on the same inputs and
compares the answers.

  cd matrix-ai-service
  .venv\\Scripts\\python.exe ..\\guide\\tools\\check_ports.py
"""

import itertools
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "matrix-ai-service"))

from src.order_ids import find_order_ids, normalize  # noqa: E402
from src.policy_engine import decide  # noqa: E402
from src.reply_guard import check, fallback_reply  # noqa: E402

TEXTS = [
    "איפה ORD-1006 ומתי היא תגיע?", "cancel ord 1001 and ORD1001", "הזמנהORD-1001", "ORD-12345", "ord-1001, ORD 1002",
    "no order here", "XORD-1001", "ORD-1001ORD-1002",
]
RAW = ["ord-1001", "ORD 1001", "ORD1001", " ORD-1001 ", "ORD-12", "x", "ORD-1001x"]

ORDERS = [
    {"status": s, "estimated_delivery": e, "delivered_at": d}
    for s, e, d in [
        ("processing", "2026-09-25", None), ("shipped", "2026-09-20", None), ("shipped", "2026-09-24", None),
        ("delivered", "2026-09-12", "2026-09-12"), ("delivered", "2026-09-01", "2026-09-01"),
        ("delivered", "2026-09-08", "2026-09-08"), ("delivered", "2026-09-07", "2026-09-07"),
        ("cancelled", "2026-09-25", None), ("on_hold", "2026-09-10", None),
    ]
]
INTENTS = ["order_status", "delivery_delay", "cancel", "return", "damaged_item", "other"]
STATES = ["opened", "unopened", "unknown"]
TODAYS = ["2026-09-22", "2026-09-24", "2026-09-26"]

REPLIES = [
    ("שלום רב,\n\nאנו מעדכנים כי בקשתך שמספרה SR-000003 נקלטה במערכת. נבקש להבהיר כי קליטת הבקשה אינה מהווה אישור סופי לתוצאה.", "ORD-1003", ["2026-09-12"], "SR-000003"),
    ("Your order ORD-1003 was delivered on 12.09.2026. Request SR-000003 was received.", "ORD-1003", ["2026-09-12"], "SR-000003"),
    ("your order ORD-1001 was cancelled and you will receive a refund within 3 days", "ORD-1001", ["2026-09-25"], None),
    ("Your order ORD-1001 is processing. ORD-1005 ships on September 24.", "ORD-1001", ["2026-09-25"], None),
    ("We opened SR-000009 (POL-03). You may get 50 NIS compensation.", "ORD-1002", ["2026-09-20"], "SR-000002"),
    ("ההזמנה תגיע מחר ב-25 בספטמבר", "ORD-1001", ["2026-09-25"], None),
    ("ההזמנה יבוטל ב-26/09/2026", "ORD-1001", ["2026-09-25"], None),
    ("It arrives on the 25th of September 2026.", "ORD-1001", ["2026-09-25"], None),
    ("Price is $20", "ORD-1001", [], None),
    ("Nothing risky here.", "ORD-1001", [], "SR-000001"),
]

KINDS = [("מספר הזמנה לא מורשה", "order"), ("תאריך שלא מופיע", "date"), ("לשון התחייבות", "commitment"), ("מועד יחסי", "relative"),
         ("סכום/מטבע", "currency"), ("קוד או מונח פנימי", "internal"), ("מספר בקשה לא מורשה", "sr_foreign"), ("מספר בקשת השירות לא מופיע", "sr_missing")]


def kind_of(msg):
    return next(k for p, k in KINDS if msg.startswith(p))


def py_results():
    out = {"normalize": [normalize(r) for r in RAW], "find": [find_order_ids(t) for t in TEXTS], "decide": [], "guard": [], "fallback": []}
    for (o, i, s, t) in itertools.product(ORDERS, INTENTS, STATES, TODAYS):
        try:
            d = decide(i, o, s, date.fromisoformat(t))
            out["decide"].append([d.action, d.service_request_type, d.source_ids])
        except Exception as exc:  # noqa: BLE001
            out["decide"].append(["error", type(exc).__name__, []])
    for reply, oid, dates, sr in REPLIES:
        out["guard"].append(sorted(kind_of(v) for v in check(reply, oid, dates, sr)))
    for action, sr, lang in itertools.product(["reply", "clarify", "escalate"], [None, "SR-000007"], ["he", "en"]):
        out["fallback"].append(fallback_reply(action, sr, lang))
    return out


NODE = """
const L = require(process.argv[1]);
const A = JSON.parse(process.argv[2]);
const out = {normalize: A.RAW.map(L.normalize), find: A.TEXTS.map(L.findOrderIds), decide: [], guard: [], fallback: []};
for (const o of A.ORDERS) for (const i of A.INTENTS) for (const s of A.STATES) for (const t of A.TODAYS) {
  const d = L.decide(i, o, s, t); out.decide.push([d.action, d.sr, d.sources]);
}
for (const [reply, oid, dates, sr] of A.REPLIES) out.guard.push(L.guardCheck(reply, oid, dates, sr).map(v => v.kind).sort());
for (const action of ["reply","clarify","escalate"]) for (const sr of [null,"SR-000007"]) for (const lang of ["he","en"]) out.fallback.push(L.fallbackReply(action, sr, lang));
console.log(JSON.stringify(out));
"""


def main():
    py = py_results()
    args = json.dumps({"RAW": RAW, "TEXTS": TEXTS, "ORDERS": ORDERS, "INTENTS": INTENTS, "STATES": STATES, "TODAYS": TODAYS, "REPLIES": REPLIES}, ensure_ascii=False)
    res = subprocess.run(["node", "-e", NODE, str(ROOT / "guide" / "assets" / "logic.js"), args], capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        print(res.stderr)
        sys.exit(1)
    js = json.loads(res.stdout)
    bad = 0
    for key in py:
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(py[key], js[key])) if a != b]
        print(f"{key:10} {len(py[key]):5} cases  {'OK' if not diffs else str(len(diffs)) + ' DIFFERENT'}")
        for i, a, b in diffs[:5]:
            print("   case", i, "python:", a, "js:", b)
        bad += len(diffs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
