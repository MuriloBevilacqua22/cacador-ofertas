"""Quais categorias conferir em cada execução (spec §6: rápidas toda hora, demais a cada 3 h)."""
from datetime import datetime
from zoneinfo import ZoneInfo

SP = ZoneInfo("America/Sao_Paulo")
FAST = ("gpu", "iphone")
SLOW = ("cpu", "placa_mae", "ram", "perifericos", "controles")


def categories_due(now: datetime) -> list[str]:
    if now.astimezone(SP).hour % 3 == 0:
        return [*FAST, *SLOW]
    return list(FAST)
