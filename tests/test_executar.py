from datetime import datetime
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from coletor import executar
from coletor.catalogo import load_catalog
from coletor.executar import run_collection
from coletor.http import PageBlocked
from coletor.modelos import RawOffer

SP = ZoneInfo("America/Sao_Paulo")
NOW_SLOW_HOUR = datetime(2026, 11, 18, 9, 5, tzinfo=SP)
NOW_OFF_HOUR = datetime(2026, 11, 18, 10, 5, tzinfo=SP)
CATALOG = load_catalog()


class FakeOk:
    needs_browser = False

    def __init__(self, sid):
        self.id, self.name, self.terms = sid, sid.title(), []

    def search_urls(self, term):
        self.terms.append(term)
        return [f"https://{self.id}/{term}"]

    def parse_search(self, html, url):
        if url.endswith("rtx 4070"):
            return [RawOffer(self.id, "Placa de Vídeo RTX 4070 12GB", f"https://{self.id}/p/1", D("4000"), D("3800"), True),
                    RawOffer(self.id, "Capa iPhone 16 Pro", f"https://{self.id}/p/2", D("50"), None, True)]
        return []


class FakeBlocked(FakeOk):
    def parse_search(self, html, url):
        raise PageBlocked("a loja bloqueou o acesso (HTTP 403)")


class FakeClient:
    def get(self, url):
        return "<html></html>"

    def close(self):
        pass


def fake_client(adapter):
    return FakeClient()


def store_row(conn, sid):
    return conn.execute("select last_error, last_success_at from stores where id = %s", (sid,)).fetchone()


def test_one_store_blocked_others_saved(conn):
    s = run_collection(conn, {"a": FakeOk("a"), "b": FakeBlocked("b")}, CATALOG, fake_client, NOW_SLOW_HOUR)
    assert "b" in s.store_errors and "bloqueou" in s.store_errors["b"]
    assert s.prices_saved == 2
    err_b, _ = store_row(conn, "b")
    err_a, ok_a = store_row(conn, "a")
    assert err_b and err_a is None and ok_a is not None
    assert conn.execute("select count(*) from listings l where l.store_id = 'b'").fetchone()[0] == 0


def test_unmatched_counted(conn):
    s = run_collection(conn, {"a": FakeOk("a")}, CATALOG, fake_client, NOW_SLOW_HOUR)
    assert (s.offers_seen, s.matched, s.unmatched) == (2, 1, 1)


def test_only_fast_categories_off_hour(conn):
    a = FakeOk("a")
    run_collection(conn, {"a": a}, CATALOG, fake_client, NOW_OFF_HOUR)
    fast_terms = set(CATALOG.terms_for("gpu") + CATALOG.terms_for("iphone"))
    assert set(a.terms) == fast_terms


def test_run_summary_saved(conn):
    s = run_collection(conn, {"a": FakeOk("a")}, CATALOG, fake_client, NOW_SLOW_HOUR)
    summary = conn.execute("select summary from runs where id = %s", (s.run_id,)).fetchone()[0]
    assert summary["prices_saved"] == s.prices_saved and summary["store_errors"] == {}


def test_main_returns_1_when_all_fail(monkeypatch, conn):
    monkeypatch.setattr(executar, "_open_db", lambda: conn)
    monkeypatch.setattr(executar, "STORES", {"b": FakeBlocked("b")})
    monkeypatch.setattr(executar, "_make_client", fake_client)
    assert executar.main() == 1


def test_main_returns_0_when_one_works(monkeypatch, conn):
    monkeypatch.setattr(executar, "_open_db", lambda: conn)
    monkeypatch.setattr(executar, "STORES", {"a": FakeOk("a"), "b": FakeBlocked("b")})
    monkeypatch.setattr(executar, "_make_client", fake_client)
    assert executar.main() == 0


def test_main_without_database_url_fails_clearly(monkeypatch):
    with pytest.raises(SystemExit) as e:
        executar._open_db()
    assert "DATABASE_URL" in str(e.value)
