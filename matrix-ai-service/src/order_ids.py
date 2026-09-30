"""Deterministic order-id handling. The model proposes order ids; this module
is how the code verifies them (design §7: "המודל מוצא, הקוד מוודא")."""

import re

# Lookarounds instead of \b: Python treats Hebrew letters as word characters,
# so \b would fail on "הזמנהORD-1001"-style joins. Accepts ORD-1001, ORD 1001,
# ORD1001 and any casing; always normalizes to ORD-1001.
_ORD = re.compile(r"(?i)(?<![A-Za-z0-9])ORD[-\s]?(\d{4})(?!\d)")


def normalize(raw: str) -> str | None:
    match = _ORD.fullmatch(raw.strip())
    return f"ORD-{match.group(1)}" if match else None


def find_order_ids(text: str) -> list[str]:
    """Every order id written in the text, normalized, de-duplicated, in order."""
    found: list[str] = []
    for match in _ORD.finditer(text):
        oid = f"ORD-{match.group(1)}"
        if oid not in found:
            found.append(oid)
    return found
