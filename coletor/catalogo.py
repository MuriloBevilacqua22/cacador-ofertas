"""Catálogo do recorte e reconhecimento de a que modelo cada anúncio pertence."""
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from coletor.modelos import Condition, Match, RawOffer

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "catalogo.yaml"
_STORAGE = re.compile(r"\b(64|128|256|512)\s*gb\b|\b([12])\s*tb\b")
_SLUG_STOP = {"de", "da", "do", "para", "com", "e", "gamer", "processador", "placa", "mae",
              "memoria", "ram", "sem", "fio"}


def normalize(text: str) -> str:
    """Minúsculas, sem acento, só letras/números separados por um espaço."""
    t = re.sub(r"[\u2122\u00ae\u00a9]", " ", text)  # ™ ® © viram espaço, não "tm"
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _has(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _any(text: str, terms: list[str]) -> bool:
    return any(_has(text, t) for t in terms)


@dataclass
class ModelRule:
    id: str
    name: str
    pattern: re.Pattern
    require: re.Pattern | None
    priority: str


@dataclass
class Category:
    id: str
    kind: Literal["fixed", "open"]
    search_terms: list[str]
    exclude: list[str] = field(default_factory=list)
    require_any: list[str] = field(default_factory=list)
    require_all: list[list[str]] = field(default_factory=list)
    models: list[ModelRule] = field(default_factory=list)
    allow_used: bool = False
    storage_required: bool = False


@dataclass
class Catalog:
    categories: dict[str, Category]
    global_exclude: list[str] = field(default_factory=list)
    used_terms: list[str] = field(default_factory=list)

    def terms_for(self, category_id: str) -> list[str]:
        return list(self.categories[category_id].search_terms)


def load_catalog(path: Path = DEFAULT_PATH) -> Catalog:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cats = {}
    for cid, c in raw["categories"].items():
        models = [ModelRule(m["id"], str(m["name"]), re.compile(m["pattern"]),
                            re.compile(m["require"]) if m.get("require") else None,
                            m.get("priority", "baixa"))
                  for m in c.get("models", [])]
        cats[cid] = Category(
            id=cid, kind=c["kind"], search_terms=c["search_terms"],
            exclude=[normalize(t) for t in c.get("exclude", [])],
            require_any=[normalize(t) for t in c.get("require_any", [])],
            require_all=[[normalize(t) for t in g] for g in c.get("require_all", [])],
            models=models, allow_used=c.get("allow_used", False),
            storage_required=c.get("storage_required", False))
    return Catalog(cats, [normalize(t) for t in raw.get("global_exclude", [])],
                   [normalize(t) for t in raw.get("used_terms", [])])


def _slug(text: str) -> str:
    words = [w for w in text.split() if w not in _SLUG_STOP]
    return "-".join(words)[:80].rstrip("-")


def _match_category(t: str, title: str, used: bool, cat: Category) -> Match | None:
    if _any(t, cat.exclude):
        return None
    if used and not cat.allow_used:
        return None
    condition = Condition.USED if used else Condition.NEW
    if cat.kind == "open":
        if not cat.require_all or not all(_any(t, g) for g in cat.require_all):
            return None
        return Match(f"{cat.id}:{_slug(t)}", title.strip(), cat.id, condition, "baixa")
    if not _any(t, cat.require_any):
        return None
    for rule in cat.models:
        if not rule.pattern.search(t) or (rule.require and not rule.require.search(t)):
            continue
        model_id, name = rule.id, rule.name
        if cat.storage_required:
            s = _STORAGE.search(t)
            if not s:
                return None
            cap = f"{s.group(1)}gb" if s.group(1) else f"{s.group(2)}tb"
            model_id, name = f"{model_id}-{cap}", f"{name} {cap.upper()}"
        if used:
            model_id, name = f"{model_id}-seminovo", f"{name} (seminovo)"
        return Match(model_id, name, cat.id, condition, rule.priority)
    return None


def match_offer(offer: RawOffer, catalog: Catalog) -> Match | None:
    """Modelo do catálogo a que o anúncio pertence, ou None se não der para ter certeza."""
    t = normalize(offer.title)
    if _any(t, catalog.global_exclude):
        return None
    used = _any(t, catalog.used_terms)
    ordered = sorted(catalog.categories.values(), key=lambda c: c.kind != "fixed")
    for cat in ordered:
        m = _match_category(t, offer.title, used, cat)
        if m:
            return m
    return None
