"""Estatísticas de preço por modelo, usadas pelo site e pelos alertas.

Só preços em estoque. "Dia" é o dia no fuso America/Sao_Paulo; o dia de hoje
fica fora da média, do mínimo e da contagem de histórico, para que uma queda
de hoje seja comparada com o passado.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import psycopg

TZ = "America/Sao_Paulo"
CURRENT_WINDOW = timedelta(hours=6)


@dataclass(frozen=True)
class PriceStats:
    model_id: str
    current_best: Decimal | None
    current_store: str | None
    current_url: str | None
    avg_30d: Decimal | None
    min_90d: Decimal | None
    change_1d_pct: float | None
    history_days: int


_DAILY = """
    with daily as (
        select (p.collected_at at time zone %(tz)s)::date as day, min(p.comparable_price) as low
        from prices p join listings l on l.id = p.listing_id
        where l.model_id = %(model)s and p.in_stock
          and p.collected_at >= %(since)s
        group by 1
    ), today as (select (%(now)s::timestamptz at time zone %(tz)s)::date as d)
    select
        (select round(avg(low), 2) from daily, today where day < d and day >= d - 30),
        (select min(low) from daily, today where day < d and day >= d - 90),
        (select low from daily, today where day = d - 1),
        (select count(*) from daily, today where day < d)
"""

_CURRENT = """
    select p.comparable_price, l.store_id, l.url
    from prices p join listings l on l.id = p.listing_id
    where l.model_id = %(model)s and p.in_stock
      and p.collected_at > %(window)s and p.collected_at <= %(now)s
    order by p.comparable_price, p.collected_at desc
    limit 1
"""


def price_stats(conn: psycopg.Connection, model_id: str, now: datetime) -> PriceStats:
    params = {"tz": TZ, "model": model_id, "now": now,
              "since": now - timedelta(days=92), "window": now - CURRENT_WINDOW}
    avg_30d, min_90d, yesterday, history_days = conn.execute(_DAILY, params).fetchone()
    current = conn.execute(_CURRENT, params).fetchone()
    best, store, url = current if current else (None, None, None)
    change = None
    if best is not None and yesterday:
        change = float(((best - yesterday) / yesterday * 100).quantize(Decimal("0.1"), ROUND_HALF_UP))
    return PriceStats(model_id, best, store, url, avg_30d, min_90d, change, int(history_days))
