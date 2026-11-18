"""Adaptadores das lojas.

Contrato de cada adaptador:
- search_urls(term) devolve até 2 URLs (páginas 1 e 2 da busca).
- parse_search(html, url) devolve os anúncios da página. Página que diz
  explicitamente "nenhum resultado" → []. Página sem a estrutura de
  produtos (captcha, bloqueio, layout desconhecido) → PageBlocked.
"""
from typing import Protocol

from coletor.http import PageBlocked  # noqa: F401  (reexportado para os adaptadores)
from coletor.modelos import RawOffer


class StoreAdapter(Protocol):
    id: str
    name: str
    needs_browser: bool

    def search_urls(self, term: str) -> list[str]: ...

    def parse_search(self, html: str, url: str) -> list[RawOffer]: ...


STORES: dict[str, StoreAdapter] = {}


def register(adapter: StoreAdapter) -> StoreAdapter:
    STORES[adapter.id] = adapter
    return adapter
