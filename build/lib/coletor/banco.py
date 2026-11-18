"""Gravação das coletas no Postgres (Supabase em produção)."""
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from coletor.modelos import Match, RawOffer

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migracoes"


def connect(dsn: str) -> psycopg.Connection:
    conn = psycopg.connect(dsn, autocommit=True)
    conn.execute("set time zone 'UTC'")
    return conn


def apply_migrations(conn: psycopg.Connection) -> None:
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        with conn.transaction():
            conn.execute(sql_file.read_text(encoding="utf-8"))


def start_run(conn: psycopg.Connection, started_at: datetime) -> int:
    with conn.transaction():
        return conn.execute("insert into runs (started_at) values (%s) returning id",
                            (started_at,)).fetchone()[0]


def finish_run(conn: psycopg.Connection, run_id: int, finished_at: datetime, summary: dict) -> None:
    with conn.transaction():
        conn.execute("update runs set finished_at = %s, summary = %s where id = %s",
                     (finished_at, Jsonb(summary), run_id))


def _ensure_store(conn: psycopg.Connection, store_id: str, name: str | None = None) -> None:
    conn.execute("insert into stores (id, name) values (%s, %s) on conflict (id) do update "
                 "set name = coalesce(%s, stores.name)", (store_id, name or store_id, name))


def save_offers(conn: psycopg.Connection, run_id: int, store_id: str,
                items: list[tuple[RawOffer, Match | None]], seen_at: datetime) -> int:
    """Grava anúncios e preços de uma loja numa transação. Retorna linhas de preço gravadas."""
    saved = 0
    with conn.transaction():
        _ensure_store(conn, store_id)
        for offer, match in items:
            if match:
                conn.execute(
                    "insert into models (id, category, name, condition, priority) values (%s,%s,%s,%s,%s) "
                    "on conflict (id) do update set name = excluded.name, priority = excluded.priority",
                    (match.model_id, match.category, match.model_name, str(match.condition), match.priority))
            listing_id = conn.execute(
                """insert into listings (store_id, url, title, model_id, category, seller, seller_rating,
                                         seller_sales, official_store, first_seen_at, last_seen_at)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (url) do update set title = excluded.title, model_id = excluded.model_id,
                       category = excluded.category, seller = excluded.seller,
                       seller_rating = excluded.seller_rating, seller_sales = excluded.seller_sales,
                       official_store = excluded.official_store, last_seen_at = excluded.last_seen_at
                   returning id""",
                (store_id, offer.url, offer.title, match.model_id if match else None,
                 match.category if match else None, offer.seller, offer.seller_rating,
                 offer.seller_sales, offer.official_store, seen_at, seen_at)).fetchone()[0]
            if offer.comparable_price is None:
                continue
            cur = conn.execute(
                """insert into prices (listing_id, run_id, collected_at, price, cash_price,
                                       comparable_price, in_stock)
                   values (%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""",
                (listing_id, run_id, seen_at, offer.price, offer.cash_price,
                 offer.comparable_price, offer.in_stock))
            saved += cur.rowcount
    return saved


def record_store_result(conn: psycopg.Connection, store_id: str, name: str, ok: bool,
                        error: str | None, at: datetime) -> None:
    with conn.transaction():
        _ensure_store(conn, store_id, name)
        if ok:
            conn.execute("update stores set last_success_at = %s, last_error = null, "
                         "last_error_at = null where id = %s", (at, store_id))
        else:
            conn.execute("update stores set last_error = %s, last_error_at = %s where id = %s",
                         (error, at, store_id))
