"""Leitura de preços escritos no formato brasileiro."""
import re
from decimal import Decimal

# 1.899,90 | 1899,90 | 1.899 | 899
_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?")


def parse_brl(text: str | None) -> Decimal | None:
    """Último valor em reais do texto; None se não houver valor ou se for zero."""
    if not text:
        return None
    achados = _NUMERO.findall(text)
    if not achados:
        return None
    valor = Decimal(achados[-1].replace(".", "").replace(",", "."))
    return valor if valor > 0 else None
