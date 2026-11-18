"""Uma execução do robô: busca as lojas, reconhece os produtos e grava no banco.

Uso: DATABASE_URL=... python -m coletor.executar
"""
import os
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from coletor.agenda import categories_due
from coletor.banco import (apply_migrations, connect, finish_run, record_store_result,
                           save_offers, start_run)
from coletor.catalogo import Catalog, load_catalog, match_offer
from coletor.http import FetchError, PageBlocked, PoliteClient
from coletor.lojas import StoreAdapter
from coletor.lojas.todas import STORES
from coletor.modelos import RawOffer


@dataclass
class RunSummary:
    run_id: int
    offers_seen: int = 0
    matched: int = 0
    unmatched: int = 0
    prices_saved: int = 0
    store_errors: dict[str, str] = field(default_factory=dict)


def _terms(catalog: Catalog, categories: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for c in categories:
        for t in catalog.terms_for(c):
            seen.setdefault(t, None)
    return list(seen)


def _describe(e: Exception) -> str:
    if isinstance(e, PageBlocked):
        return f"Bloqueio: {e}"
    if isinstance(e, FetchError):
        return f"Falha ao ler a loja: {e}"
    return f"Erro inesperado: {type(e).__name__}: {e}"


def _collect_store(adapter: StoreAdapter, terms: list[str],
                   make_client: Callable[[StoreAdapter], PoliteClient]) -> list[RawOffer]:
    """Busca todos os termos numa loja. Qualquer erro interrompe a loja inteira."""
    client = make_client(adapter)
    by_url: dict[str, RawOffer] = {}
    try:
        for term in terms:
            for url in adapter.search_urls(term):
                for offer in adapter.parse_search(client.get(url), url):
                    by_url.setdefault(offer.url, offer)
    finally:
        client.close()
    return list(by_url.values())


def run_collection(conn, stores: dict[str, StoreAdapter], catalog: Catalog,
                   make_client: Callable[[StoreAdapter], PoliteClient], now: datetime) -> RunSummary:
    summary = RunSummary(run_id=start_run(conn, now))
    terms = _terms(catalog, categories_due(now))
    with ThreadPoolExecutor(max_workers=max(1, len(stores))) as pool:
        futures = {sid: pool.submit(_collect_store, a, terms, make_client) for sid, a in stores.items()}
    for sid, fut in futures.items():
        adapter = stores[sid]
        try:
            offers = fut.result()
        except Exception as e:  # noqa: BLE001 — uma loja nunca derruba as outras
            summary.store_errors[sid] = _describe(e)
            record_store_result(conn, sid, adapter.name, False, summary.store_errors[sid], now)
            continue
        items = [(o, match_offer(o, catalog)) for o in offers]
        summary.offers_seen += len(items)
        summary.matched += sum(1 for _, m in items if m)
        summary.unmatched += sum(1 for _, m in items if not m)
        summary.prices_saved += save_offers(conn, summary.run_id, sid, items, now)
        record_store_result(conn, sid, adapter.name, True, None, now)
    finish_run(conn, summary.run_id, datetime.now(timezone.utc),
               {k: v for k, v in asdict(summary).items() if k != "run_id"})
    return summary


def _open_db():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL não configurada: cadastre o segredo no GitHub.")
    return connect(dsn)


def _make_client(adapter: StoreAdapter) -> PoliteClient:
    if getattr(adapter, "needs_browser", False):
        from coletor.http import BrowserClient
        return BrowserClient()
    return PoliteClient()


def main() -> int:
    conn = _open_db()
    apply_migrations(conn)
    s = run_collection(conn, STORES, load_catalog(), _make_client, datetime.now(timezone.utc))
    print(f"Execução {s.run_id}: {s.offers_seen} anúncios, {s.matched} reconhecidos, "
          f"{s.unmatched} não reconhecidos, {s.prices_saved} preços gravados.")
    for sid, err in s.store_errors.items():
        print(f"  ⚠ {sid}: {err}")
    ok_stores = len(STORES) - len(s.store_errors)
    return 0 if STORES and ok_stores > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
