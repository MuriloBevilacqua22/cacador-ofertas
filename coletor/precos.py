"""Leitura de preços de texto (formato brasileiro, e o americano que algumas lojas usam)."""
import re
from decimal import Decimal

_NUMERO = re.compile(r"\d[\d.,]*\d|\d")
_CENTAVOS = re.compile(r"[.,](\d{1,2})$")


def parse_brl(text: str | None) -> Decimal | None:
    """Último valor do texto; None se não houver valor ou se for zero.

    O separador seguido de 1 ou 2 dígitos no fim é o dos centavos
    ("1.899,90", "4,299.99", "899.90"); qualquer outro é de milhar ("1.899").
    """
    if not text:
        return None
    achados = _NUMERO.findall(text)
    if not achados:
        return None
    bruto = achados[-1]
    centavos = _CENTAVOS.search(bruto)
    if centavos:
        inteiro = re.sub(r"[.,]", "", bruto[:centavos.start()])
        valor = Decimal(f"{inteiro}.{centavos.group(1)}")
    else:
        valor = Decimal(re.sub(r"[.,]", "", bruto))
    return valor if valor > 0 else None
