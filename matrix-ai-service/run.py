"""CLI entrypoint. Source: design doc section 21 (lines 500-504), A2 (line 69)."""

import argparse
import json
import logging
import os
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()  # must run before importing src.agent/src.llm read env vars

from src.agent import handle  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="עוזר AI לשירות לקוחות באתר מסחר")
    parser.add_argument("customer_id")
    parser.add_argument("message")
    parser.add_argument("--context", default=None, help='הקשר לתשובת המשך, למשל "return:ORD-1003"')
    parser.add_argument("--simulate-outage", action="store_true", help="מדמה שירות הזמנות לא זמין")
    parser.add_argument("--today", default=os.getenv("TODAY", "2026-09-22"), help="YYYY-MM-DD")
    parser.add_argument("-v", "--verbose", action="store_true", help="מציג לוגים (ספק, latency, guard) ל-stderr")
    args = parser.parse_args()

    # Logs go to stderr only — stdout stays pure JSON (design line 359: logs
    # keep identifiers/timings, never full free text — no message content here).
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        stream=sys.stderr,
        format="%(levelname)s %(message)s",
    )

    result = handle(
        customer_id=args.customer_id,
        message=args.message,
        context=args.context,
        today=date.fromisoformat(args.today),
        simulate_outage=args.simulate_outage,
    )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
