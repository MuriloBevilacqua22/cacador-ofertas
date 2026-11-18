import json
import re
from decimal import Decimal as D
from pathlib import Path

import pytest

from coletor.http import PageBlocked
from coletor.lojas.kabum import KabumAdapter

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "kabum"
URL = "https://www.kabum.com.br/busca/rtx-4070"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_parses_products():
    offers = KabumAdapter().parse_search(fixture("busca_rtx_4070.html"), URL)
    assert len(offers) == 46
    o = offers[0]
    assert o.store == "kabum" and o.url.startswith("https://www.kabum.com.br/produto/")
    assert "4070" in o.title.lower() and o.comparable_price > 100


def test_flash_offer_price_wins():
    o = KabumAdapter().parse_search(fixture("busca_headset_corsair.html"), URL)[0]
    assert o.title == ("Headset Gamer Sem Fio Corsair HS80 Premium, RGB, Surround, Dolby Atmos, "
                       "Wireless, Drivers 50mm, Preto - CA-9011235-NA")
    assert (o.price, o.cash_price, o.in_stock) == (D("764.69"), D("649.99"), True)
    assert o.url == ("https://www.kabum.com.br/produto/216705/headset-gamer-sem-fio-corsair-hs80-premium-"
                     "rgb-surround-dolby-atmos-wireless-drivers-50mm-preto-ca-9011235-na")
    assert o.seller == "KaBuM!" and o.official_store is True


def test_marketplace_seller_not_official():
    o = KabumAdapter().parse_search(fixture("busca_rtx_4070.html"), URL)[0]
    assert o.seller == "2Eletro" and o.official_store is False
    assert (o.price, o.cash_price) == (D("17751.76"), D("15089"))


def test_data_as_json_string_is_parsed():
    offers = KabumAdapter().parse_search(fixture("busca_iphone_16_pro.html"), URL)
    assert len(offers) == 17 and "iphone" in offers[0].title.lower()


def _edit_first(html: str, **changes) -> str:
    m = re.search(r'(<script id="__NEXT_DATA__"[^>]*>)(.*?)(</script>)', html, re.S)
    d = json.loads(m.group(2))
    data = d["props"]["pageProps"]["data"]
    item = data["catalogServer"]["data"][0]
    for k, v in changes.items():
        if k == "isOpenbox":
            item["flags"]["isOpenbox"] = v
        else:
            item[k] = v
    return html[:m.start(2)] + json.dumps(d) + html[m.end(2):]


def test_out_of_stock_flagged():
    html = _edit_first(fixture("busca_headset_corsair.html"), available=False)
    assert KabumAdapter().parse_search(html, URL)[0].in_stock is False


def test_open_box_marked_in_title():
    html = _edit_first(fixture("busca_headset_corsair.html"), isOpenbox=True)
    assert KabumAdapter().parse_search(html, URL)[0].title.startswith("Open Box ")


def test_empty_page_two_returns_empty_list():
    assert KabumAdapter().parse_search(fixture("busca_rtx_4070_p2.html"), URL) == []


def test_captcha_page_raises():
    with pytest.raises(PageBlocked):
        KabumAdapter().parse_search("<html><body>Verifique se você é humano</body></html>", URL)


def test_search_urls_two_pages():
    urls = KabumAdapter().search_urls("rtx 4070")
    assert urls == ["https://www.kabum.com.br/busca/rtx-4070",
                    "https://www.kabum.com.br/busca/rtx-4070?page_number=2"]
