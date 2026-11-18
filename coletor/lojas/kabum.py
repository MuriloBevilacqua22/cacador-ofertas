"""Kabum: os produtos vêm em JSON dentro da página (__NEXT_DATA__)."""
import json
import re
from decimal import Decimal
from urllib.parse import quote

from coletor.http import PageBlocked
from coletor.lojas import register
from coletor.modelos import RawOffer

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _money(v) -> Decimal | None:
    if v in (None, "", 0):
        return None
    d = Decimal(str(v)).quantize(Decimal("0.01"))
    return d if d > 0 else None


class KabumAdapter:
    id = "kabum"
    name = "Kabum"
    needs_browser = False

    def search_urls(self, term: str) -> list[str]:
        base = f"https://www.kabum.com.br/busca/{quote('-'.join(term.lower().split()))}"
        return [base, f"{base}?page_number=2"]

    def parse_search(self, html: str, url: str) -> list[RawOffer]:
        m = _NEXT_DATA.search(html)
        try:
            data = json.loads(m.group(1))["props"]["pageProps"]["data"]
            if isinstance(data, str):
                data = json.loads(data)
            products = data["catalogServer"]["data"]
        except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as e:
            raise PageBlocked("a página da Kabum veio sem a lista de produtos") from e
        return [self._offer(p) for p in products]

    def _offer(self, p: dict) -> RawOffer:
        flash = p.get("offer") or {}
        price = _money(flash.get("price")) or _money(p.get("price"))
        cash = _money(flash.get("priceWithDiscount")) or _money(p.get("priceWithDiscount"))
        flags = p.get("flags") or {}
        title = str(p.get("name", "")).strip()
        if flags.get("isOpenbox"):
            title = f"Open Box {title}"
        return RawOffer(
            store=self.id,
            title=title,
            url=f"https://www.kabum.com.br/produto/{p['code']}/{p.get('friendlyName', '')}".rstrip("/"),
            price=price,
            cash_price=cash,
            in_stock=bool(p.get("available")),
            seller=p.get("sellerName") or None,
            official_store=not flags.get("isMarketplace", False),
        )


register(KabumAdapter())
