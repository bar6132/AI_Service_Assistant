import pytest

from src.models import Extraction
from src.order_ids import find_order_ids, normalize


@pytest.mark.parametrize("raw", ["ORD-1001", "ord-1001", "ORD 1001", "ORD1001", " ORD-1001 "])
def test_normalize_variants(raw):
    assert normalize(raw) == "ORD-1001"


@pytest.mark.parametrize("raw", ["ORD-101", "ORD-10011", "1001", "XORD-1001", "ORD-1001\n extra"])
def test_normalize_rejects_malformed(raw):
    assert normalize(raw) is None


def test_find_in_hebrew_sentence_dedupes_and_keeps_order():
    text = "אני רוצה לבטל את הזמנה ORD-1001, כן ord-1001, ולא את ORD 1002"
    assert find_order_ids(text) == ["ORD-1001", "ORD-1002"]


def test_find_ignores_longer_numbers():
    assert find_order_ids("מספר ORD-10011 לא קיים") == []


def test_extraction_normalizes_and_dedupes_model_output():
    e = Extraction(intent="cancel", order_ids=["ord-1001", "ORD-1001", "junk"],
                   product_state="unknown", asks_compensation=False, language="he")
    assert e.order_ids == ["ORD-1001"]
