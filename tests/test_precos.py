from decimal import Decimal

import pytest

from coletor.modelos import RawOffer
from coletor.precos import parse_brl


@pytest.mark.parametrize("text,expected", [
    ("R$ 1.899,90", Decimal("1899.90")),
    ("R$1.899", Decimal("1899")),
    ("1.899", Decimal("1899")),
    ("R$ 899,00", Decimal("899.00")),
    ("De R$ 2.199,00 por R$ 1.899,00", Decimal("1899.00")),
    ("R$ 12.499,99 à vista", Decimal("12499.99")),
    ("R$\xa01.234,56", Decimal("1234.56")),
    ("R$ 4,299.99", Decimal("4299.99")),            # formato americano (Pichau)
    ("de R$ 6,525.00 por: R$ 4,299.99", Decimal("4299.99")),
    ("R$ 899.90", Decimal("899.90")),
    ("", None),
    (None, None),
    ("Indisponível", None),
    ("R$ 0,00", None),
])
def test_parse_brl(text, expected):
    assert parse_brl(text) == expected


def test_comparable_price_prefers_cash():
    o = RawOffer("kabum", "x", "u", Decimal("2000"), Decimal("1800"), True)
    assert o.comparable_price == Decimal("1800")
    assert RawOffer("kabum", "x", "u", Decimal("2000"), None, True).comparable_price == Decimal("2000")
    assert RawOffer("kabum", "x", "u", None, None, True).comparable_price is None
