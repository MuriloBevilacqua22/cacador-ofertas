"""Tipos de dados compartilhados pelo robô."""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Condition(StrEnum):
    NEW = "novo"
    USED = "seminovo"


@dataclass(frozen=True)
class RawOffer:
    """Um anúncio como a loja mostrou, antes de saber a que modelo pertence."""
    store: str
    title: str
    url: str
    price: Decimal | None
    cash_price: Decimal | None
    in_stock: bool
    seller: str | None = None
    seller_rating: float | None = None
    seller_sales: int | None = None
    official_store: bool = False

    @property
    def comparable_price(self) -> Decimal | None:
        """Preço à vista quando houver; senão o preço normal."""
        return self.cash_price if self.cash_price is not None else self.price


@dataclass(frozen=True)
class Match:
    """A que modelo do catálogo um anúncio pertence."""
    model_id: str
    model_name: str
    category: str
    condition: Condition
    priority: str
