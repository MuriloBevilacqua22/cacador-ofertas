"""Acesso às lojas com intervalo entre requisições e tentativas limitadas."""
import time
from collections.abc import Callable

import httpx

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class FetchError(Exception):
    """A página não pôde ser lida."""


class PageBlocked(FetchError):
    """A loja bloqueou o robô ou mostrou uma página sem produtos reconhecíveis."""


class PoliteClient:
    def __init__(self, min_interval_s: float = 3.0, timeout_s: float = 20.0, retries: int = 2,
                 transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.min_interval_s = min_interval_s
        self.retries = retries
        self._sleep, self._clock = sleep, clock
        self._last: float | None = None
        self._http = httpx.Client(headers=HEADERS, timeout=timeout_s, follow_redirects=True,
                                  transport=transport)

    def _wait_turn(self) -> None:
        if self._last is not None:
            gap = self.min_interval_s - (self._clock() - self._last)
            if gap > 0:
                self._sleep(gap)
        self._last = self._clock()

    def get(self, url: str) -> str:
        last_error = ""
        for _ in range(self.retries + 1):
            self._wait_turn()
            try:
                r = self._http.get(url)
            except httpx.HTTPError as e:
                last_error = f"falha de conexão ({type(e).__name__})"
                continue
            if r.status_code in (403, 429):
                raise PageBlocked(f"a loja bloqueou o acesso (HTTP {r.status_code})")
            if r.status_code >= 500:
                last_error = f"erro na loja (HTTP {r.status_code})"
                continue
            if r.status_code >= 400:
                raise FetchError(f"página não encontrada (HTTP {r.status_code})")
            return r.text
        raise FetchError(f"{last_error} depois de {self.retries + 1} tentativas")

    def close(self) -> None:
        self._http.close()
