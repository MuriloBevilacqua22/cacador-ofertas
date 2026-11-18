"""Salva o HTML real das buscas das lojas, para virar fixture de teste.

Uso: python -m coletor.capturar --store kabum --term "rtx 4070" [--out capturas]
Roda no GitHub Actions (workflow capturar.yml), o mesmo lugar onde o robô roda.
"""
import argparse
import re
from pathlib import Path
from urllib.parse import quote, quote_plus

from coletor.http import FetchError, PoliteClient


def _kabum(term: str) -> list[str]:
    slug = "-".join(term.lower().split())
    base = f"https://www.kabum.com.br/busca/{quote(slug)}"
    return [base, f"{base}?page_number=2"]


def _pichau(term: str) -> list[str]:
    base = f"https://www.pichau.com.br/search?q={quote_plus(term)}"
    return [base, f"{base}&page=2"]


def _terabyte(term: str) -> list[str]:
    base = f"https://www.terabyteshop.com.br/busca?str={quote_plus(term)}"
    return [base, f"{base}&pagina=2"]


_BUILDERS = {"kabum": _kabum, "pichau": _pichau, "terabyte": _terabyte}


def search_urls(store: str, term: str) -> list[str]:
    from coletor.lojas import STORES
    if store in STORES:
        return STORES[store].search_urls(term)
    return _BUILDERS[store](term)


def capture(store: str, term: str, out: Path, client) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    files = []
    for i, url in enumerate(search_urls(store, term), start=1):
        path = out / f"{store}_{slug}_p{i}.html"
        try:
            html = client.get(url)
        except FetchError as e:
            html = f"<!-- ERRO: {e} -->"
        path.write_text(f"<!-- {url} -->\n{html}", encoding="utf-8")
        files.append(path)
    return files


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--store", required=True, choices=sorted(_BUILDERS))
    p.add_argument("--term", required=True)
    p.add_argument("--out", default="capturas")
    a = p.parse_args()
    for f in capture(a.store, a.term, Path(a.out), PoliteClient()):
        print(f, f.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
