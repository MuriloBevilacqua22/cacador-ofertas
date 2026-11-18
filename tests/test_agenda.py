from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from coletor.agenda import FAST, SLOW, categories_due

SP = ZoneInfo("America/Sao_Paulo")


def test_off_hour_only_fast():
    assert categories_due(datetime(2026, 11, 18, 10, 5, tzinfo=SP)) == ["gpu", "iphone"]


def test_every_third_hour_everything():
    assert set(categories_due(datetime(2026, 11, 18, 9, 5, tzinfo=SP))) == set(FAST + SLOW)


def test_hour_is_sao_paulo_time():
    # 12:07 UTC = 09:07 em São Paulo → hora múltipla de 3
    assert set(categories_due(datetime(2026, 11, 18, 12, 7, tzinfo=timezone.utc))) == set(FAST + SLOW)
    # 10:07 UTC = 07:07 em São Paulo → só rápidas
    assert categories_due(datetime(2026, 11, 18, 10, 7, tzinfo=timezone.utc)) == ["gpu", "iphone"]
