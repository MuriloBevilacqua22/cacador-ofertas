from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from coletor.banco import (apply_migrations, finish_run, record_store_result,
                           save_offers, start_run)
from coletor.modelos import Condition, Match, RawOffer

T0 = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(hours=1)
MATCH_4070 = Match("rtx-4070", "RTX 4070", "gpu", Condition.NEW, "alta")


def count(conn, table):
    return conn.execute(f"select count(*) from {table}").fetchone()[0]


def test_same_listing_twice_in_run_gives_one_price(conn):
    run = start_run(conn, T0)
    item = (RawOffer("kabum", "RTX 4070 12GB", "https://k/1", D("4000"), D("3800"), True), MATCH_4070)
    assert save_offers(conn, run, "kabum", [item, item], T0) == 1
    assert count(conn, "prices") == 1 and count(conn, "listings") == 1
    row = conn.execute("select price, cash_price, comparable_price, in_stock from prices").fetchone()
    assert row == (D("4000"), D("3800"), D("3800"), True)


def test_offer_without_price_keeps_listing_no_price(conn):
    run = start_run(conn, T0)
    item = (RawOffer("kabum", "RTX 4070 12GB", "https://k/1", None, None, False), MATCH_4070)
    assert save_offers(conn, run, "kabum", [item], T0) == 0
    assert count(conn, "listings") == 1 and count(conn, "prices") == 0


def test_unmatched_listing_has_null_model(conn):
    run = start_run(conn, T0)
    save_offers(conn, run, "kabum", [(RawOffer("kabum", "Capa", "https://k/2", D("10"), None, True), None)], T0)
    assert conn.execute("select model_id, category from listings").fetchone() == (None, None)
    assert count(conn, "models") == 0


def test_listing_updates_on_next_run(conn):
    r1 = start_run(conn, T0)
    save_offers(conn, r1, "kabum", [(RawOffer("kabum", "Velho", "https://k/1", D("10"), None, True), None)], T0)
    r2 = start_run(conn, T1)
    save_offers(conn, r2, "kabum", [(RawOffer("kabum", "RTX 4070 12GB", "https://k/1", D("9"), None, True), MATCH_4070)], T1)
    title, model, first, last = conn.execute(
        "select title, model_id, first_seen_at, last_seen_at from listings").fetchone()
    assert (title, model, first, last) == ("RTX 4070 12GB", "rtx-4070", T0, T1)
    assert count(conn, "prices") == 2
    assert conn.execute("select name, priority from models").fetchone() == ("RTX 4070", "alta")


def test_store_error_then_success_clears_error(conn):
    record_store_result(conn, "kabum", "Kabum", False, "Bloqueio: 403", T0)
    assert conn.execute("select last_error, last_error_at, last_success_at from stores").fetchone() == ("Bloqueio: 403", T0, None)
    record_store_result(conn, "kabum", "Kabum", True, None, T1)
    err, at, ok = conn.execute("select last_error, last_error_at, last_success_at from stores").fetchone()
    assert err is None and ok == T1


def test_finish_run_stores_summary(conn):
    run = start_run(conn, T0)
    finish_run(conn, run, T1, {"prices_saved": 3})
    assert conn.execute("select finished_at, summary from runs").fetchone() == (T1, {"prices_saved": 3})


def test_apply_migrations_twice_is_safe(conn):
    apply_migrations(conn)
    assert count(conn, "stores") == 0
