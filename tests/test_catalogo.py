from decimal import Decimal

import pytest

from coletor.catalogo import load_catalog, match_offer, normalize
from coletor.modelos import Condition, RawOffer

CAT = load_catalog()


def offer(title: str) -> RawOffer:
    return RawOffer("kabum", title, "https://x/1", Decimal("1"), None, True)


CASES = [
    ("Placa de Vídeo Gigabyte GeForce RTX 4070 Ti SUPER Gaming OC 16GB", "rtx-4070-ti-super"),
    ("Placa de Vídeo ASUS TUF RTX 4070 Super 12GB GDDR6X", "rtx-4070-super"),
    ("Placa de Vídeo MSI RTX 4060 Ti Ventus 2X 16GB", "rtx-4060-ti-16gb"),
    ("Placa de Vídeo MSI RTX 4060Ti 8 GB", "rtx-4060-ti-8gb"),
    ("Placa de Vídeo MSI RTX 4060 Ti Ventus 2X", None),
    ("Placa de Vídeo Galax RTX 3060 12GB", None),
    ("Placa de Vídeo Zotac RTX 3060 Ti Twin Edge 8GB", "rtx-3060-ti"),
    ("Placa de Vídeo PNY GeForce RTX 5090 32GB", "rtx-5090"),
    ("Placa de Vídeo Palit RTX 5060 8GB", "rtx-5060"),
    ("Notebook Gamer Acer Nitro RTX 4070 i7", None),
    ("PC Gamer Completo RTX 4060 Ryzen 5", None),
    ("Suporte para Placa de Vídeo RTX 4090", None),
    ("Apple iPhone 16 Pro Max 256GB Titânio-deserto", "iphone-16-pro-max-256gb"),
    ("Apple iPhone 16 Pro 512GB", "iphone-16-pro-512gb"),
    ("iPhone 16e 128GB Branco", "iphone-16e-128gb"),
    ("iPhone 17 256 GB Preto", "iphone-17-256gb"),
    ("Apple iPhone Air 1TB", "iphone-air-1tb"),
    ("iPhone 18 Pro Max 2TB Laranja", "iphone-18-pro-max-2tb"),
    ("iPhone 15 Pro 128GB Seminovo Grade A", "iphone-15-pro-128gb-seminovo"),
    ("Apple iPhone 16 Pro Max", None),
    ("Capa iPhone 16 Pro Silicone", None),
    ("Película iPhone 15 Pro Max 3D", None),
    ("iPhone 14 Pro 128GB", None),
    ("Controle Sony DualSense Edge PS5", "dualsense-edge"),
    ("Controle Sem Fio Sony DualSense PS5 Branco", "dualsense"),
    ("Controle Sem Fio Microsoft Xbox Series X|S Carbon Black", "xbox-series"),
    ("Controle Compatível PS5 Sem Fio Tipo DualSense", None),
    ("Controle Xbox Series Com Fio Genérico", None),
    ("Base Carregadora Controle DualSense", None),
    ("Placa de Vídeo RTX 4070 12GB Usada", None),
]


@pytest.mark.parametrize("title,expected", CASES)
def test_match_fixed(title, expected):
    m = match_offer(offer(title), CAT)
    assert (m.model_id if m else None) == expected


def test_seminovo_condition_and_name():
    m = match_offer(offer("iPhone 15 Pro 128GB Seminovo Grade A"), CAT)
    assert m.condition == Condition.USED and "(seminovo)" in m.model_name
    assert m.category == "iphone"


def test_priority():
    assert match_offer(offer("Apple iPhone 16 Pro Max 256GB"), CAT).priority == "alta"
    assert match_offer(offer("Apple iPhone 16 256GB"), CAT).priority == "baixa"


def test_open_category_ids():
    m = match_offer(offer("Processador AMD Ryzen 7 7800X3D AM5"), CAT)
    assert m.category == "cpu" and m.model_id.startswith("cpu:")
    assert match_offer(offer("Processador Intel Core i5-14600K LGA1700"), CAT).category == "cpu"
    assert match_offer(offer("Placa Mãe MSI B650 Tomahawk"), CAT) is None
    assert match_offer(offer("Placa-Mãe Gigabyte B760M Aorus Elite DDR5"), CAT).category == "placa_mae"
    assert match_offer(offer("Memória Kingston Fury 16GB DDR5 Notebook SODIMM"), CAT) is None
    assert match_offer(offer("Memória Kingston Fury Beast 16GB DDR4 3200MHz"), CAT).category == "ram"
    assert match_offer(offer("Mousepad Logitech G640"), CAT) is None
    assert match_offer(offer("Headset Gamer Corsair HS80 RGB"), CAT).category == "perifericos"
    assert match_offer(offer("Mouse Gamer Razer DeathAdder"), CAT) is None


def test_open_id_is_stable():
    a = match_offer(offer("Headset Gamer Corsair HS80 RGB"), CAT)
    b = match_offer(offer("Headset  Gamer CORSAIR HS80 RGB"), CAT)
    assert a.model_id == b.model_id


def test_terms_for_every_category():
    for cat in ("gpu", "iphone", "cpu", "placa_mae", "ram", "perifericos", "controles"):
        assert CAT.terms_for(cat)


def test_normalize():
    assert normalize("Placa-Mãe  ASUS") == "placa mae asus"
    assert normalize("RTX™ 4070 Ti®") == "rtx 4070 ti"
