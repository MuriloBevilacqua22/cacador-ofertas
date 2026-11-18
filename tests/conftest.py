"""Testes usam um Postgres já rodando (local ou serviço do CI).

Configurável por TEST_PG_HOST, TEST_PG_PORT, TEST_PG_USER, TEST_PG_PASSWORD.
Cada teste recebe um banco novo, criado e apagado pelo pytest-postgresql.
"""
import os

import pytest
from pytest_postgresql import factories

from coletor.banco import apply_migrations

postgresql_noproc = factories.postgresql_noproc(
    host=os.getenv("TEST_PG_HOST", "127.0.0.1"),
    port=int(os.getenv("TEST_PG_PORT", "5432")),
    user=os.getenv("TEST_PG_USER", "postgres"),
    password=os.getenv("TEST_PG_PASSWORD", "postgres"),
)
postgresql = factories.postgresql("postgresql_noproc")


@pytest.fixture
def conn(postgresql):
    postgresql.autocommit = True
    postgresql.execute("set time zone 'UTC'")
    apply_migrations(postgresql)
    return postgresql


@pytest.fixture(autouse=True)
def _no_real_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
