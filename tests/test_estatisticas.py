from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from zoneinfo import ZoneInfo

from coletor.banco import save_offers, start_run
from coletor.estatisticas import price_stats
from coletor.modelos import Condition, Match, RawOffer

SP = ZoneInfo("America/Sao_Paulo")
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=SP)
M = Match("rtx-4070", "RTX 4070", "gpu", Condition.NEW, "alta")


def put(conn, store, url, price, at, in_stock=True):
    run = start_run(conn, at)
    save_offers(conn, run, store, [(RawOffer(store, "RTX 4070 12GB", url, D(price), None, in_stock), M)], at)


def test_stats_basic(conn):
    for d in range(2, 32):
        put(conn, "kabum", "https://k/1", "4000", NOW - timedelta(days=d))
    put(conn, "kabum", "https://k/1", "3900", NOW - timedelta(days=1))
    put(conn, "kabum", "https://k/1", "3510", NOW - timedelta(hours=1))
    put(conn, "pichau", "https://p/1", "3600", NOW - timedelta(hours=2))
    s = price_stats(conn, "rtx-4070", NOW)
    assert s.current_best == D("3510") and s.current_store == "kabum"
    assert s.current_url == "https://k/1"
    assert s.avg_30d == D("3996.67")
    assert s.min_90d == D("3900") and s.change_1d_pct == -10.0 and s.history_days == 31


def test_out_of_stock_ignored(conn):
    put(conn, "kabum", "https://k/1", "4000", NOW - timedelta(days=3))
    put(conn, "kabum", "https://k/2", "100", NOW - timedelta(days=3), in_stock=False)
    put(conn, "kabum", "https://k/2", "100", NOW - timedelta(hours=1), in_stock=False)
    s = price_stats(conn, "rtx-4070", NOW)
    assert s.current_best is None and s.min_90d == D("4000")


def test_daily_min_uses_sao_paulo_day(conn):
    # 18/11 01:30 UTC = 17/11 22:30 em São Paulo: conta como ontem
    put(conn, "kabum", "https://k/1", "3000", datetime(2026, 11, 18, 1, 30, tzinfo=timezone.utc))
    put(conn, "kabum", "https://k/1", "2700", NOW - timedelta(hours=1))
    s = price_stats(conn, "rtx-4070", NOW)
    assert s.history_days == 1 and s.min_90d == D("3000") and s.change_1d_pct == -10.0


def test_older_than_90_days_ignored(conn):
    put(conn, "kabum", "https://k/1", "1000", NOW - timedelta(days=95))
    put(conn, "kabum", "https://k/1", "4000", NOW - timedelta(days=5))
    assert price_stats(conn, "rtx-4070", NOW).min_90d == D("4000")


def test_no_data(conn):
    s = price_stats(conn, "rtx-4070", NOW)
    assert (s.current_best, s.avg_30d, s.min_90d, s.change_1d_pct, s.history_days) == (None, None, None, None, 0)


def test_stale_price_not_current(conn):
    put(conn, "kabum", "https://k/1", "4000", NOW - timedelta(hours=7))
    assert price_stats(conn, "rtx-4070", NOW).current_best is None
