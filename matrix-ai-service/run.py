"""CLI entrypoint. Source: design doc section 21 (lines 500-504), A2 (line 70)."""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime

from dotenv import load_dotenv

load_dotenv()  # must run before importing src.agent/src.llm read env vars

from pydantic import ValidationError  # noqa: E402

from src.agent import handle  # noqa: E402
from src.llm import ConfigError, validate_config  # noqa: E402


def _default_today() -> str:
    """A2: dates are evaluated in Asia/Jerusalem. TODAY in .env (or --today)
    pins a fixed reference date for reproducible tests (2026-09-22)."""
    if os.getenv("TODAY"):
        return os.environ["TODAY"]
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()
    except Exception:  # noqa: BLE001 - no tz database available
        return date.today().isoformat()


def _fail(message: str, details: list | None = None) -> None:
    """The CLI contract is one JSON object on stdout, errors included."""
    payload = {"error": message}
    if details:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="עוזר AI לשירות לקוחות באתר מסחר")
    parser.add_argument("customer_id")
    parser.add_argument("message")
    parser.add_argument("--context", default=None, help='הקשר לתשובת המשך, בפורמט intent:ORD-XXXX, למשל "return:ORD-1003"')
    parser.add_argument("--simulate-outage", action="store_true", help="מדמה שירות הזמנות לא זמין")
    parser.add_argument("--today", default=_default_today(), help="YYYY-MM-DD (ברירת מחדל: TODAY מ-.env, אחרת התאריך הנוכחי)")
    parser.add_argument("-v", "--verbose", action="store_true", help="מציג לוגים (ספק, latency, guard) ל-stderr")
    args = parser.parse_args()

    # Logs go to stderr only — stdout stays pure JSON (design line 360: logs
    # keep identifiers/timings, never full free text — no message content here).
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        stream=sys.stderr,
        format="%(levelname)s %(message)s",
    )

    try:
        today = date.fromisoformat(args.today)
    except ValueError:
        _fail(f"invalid --today value (expected YYYY-MM-DD): {args.today}")

    try:
        validate_config()
    except ConfigError as exc:
        _fail(f"configuration error: {exc}")

    try:
        result = handle(
            customer_id=args.customer_id,
            message=args.message,
            context=args.context,
            today=today,
            simulate_outage=args.simulate_outage,
        )
    except ValidationError as exc:
        _fail("invalid input", [
            {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
            for err in exc.errors(include_input=False, include_url=False)
        ])
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
