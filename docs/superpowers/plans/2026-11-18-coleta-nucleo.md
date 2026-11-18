# Caçador de Ofertas — Plano 1: Núcleo de coleta

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um robô agendado no GitHub Actions que lê Kabum, Pichau e Terabyte, reconhece os produtos do recorte do Murilo, grava preço com data no Supabase e calcula as estatísticas (média 30 dias, menor em 90 dias, variação no dia) que o site e os alertas vão consumir.

**Architecture:** Pacote Python `coletor`. Cada loja é um adaptador que monta URLs de busca e transforma HTML em `RawOffer`. Um catálogo YAML decide a que modelo cada anúncio pertence. O orquestrador busca as lojas em paralelo (uma thread por loja, com intervalo educado), grava tudo em Postgres numa transação por loja e registra a saúde de cada loja. As estatísticas saem de SQL sobre o histórico.

**Tech Stack:** Python ≥ 3.12, httpx, selectolax (parse HTML), PyYAML, psycopg 3, pytest + pytest-postgresql (Postgres 16 local nos testes), GitHub Actions (cron), Supabase (Postgres gerenciado, plano grátis).

**Spec:** `docs/superpowers/specs/2026-11-18-cacador-ofertas-design.md`

**Planos seguintes (fora deste):** 2 · Site · 3 · Alertas Telegram (critérios de alerta) · 4 · Amazon, Mercado Livre, Compras Paraguai e câmbio (inclui filtro de vendedor confiável) · 5 · AliExpress, Shopee e cupons.

## Global Constraints

- Custo zero: só planos gratuitos. **Repositório público** no GitHub (minutos de Actions ilimitados; no privado, rodar de hora em hora estoura os 2.000 min/mês). Nenhum segredo no código: `DATABASE_URL` só em GitHub Secrets / variável de ambiente.
- Respeito às lojas: intervalo mínimo de **3 s** entre requisições à mesma loja; no máximo **2 páginas** por termo de busca.
- Frequência (spec §6): `gpu` e `iphone` toda hora; demais categorias a cada 3 horas.
- Datas gravadas em UTC (`timestamptz`). "Dia" das estatísticas = fuso `America/Sao_Paulo`.
- Preço comparável = preço à vista (Pix/boleto) quando a loja mostrar; senão o preço normal. *(Chamada minha, não está na spec.)*
- Anúncio que o catálogo não reconhece com segurança fica com `model_id NULL` e nunca entra em estatística (spec §6).
- Falha de uma loja nunca derruba as outras e sempre fica registrada em `stores.last_error` (spec §4).
- Seminovo só existe para iPhone, com `model_id` próprio (sufixo `-seminovo`); seminovo de outras categorias é descartado. Memória RAM de notebook (SODIMM) fica de fora. *(Chamadas minhas.)*
- Todo texto gravado para o usuário (erros de loja, nomes de modelo) em português.

## Review Focus

1. **Título que cita a placa mas não é placa** ("Notebook Gamer RTX 4070", "PC Gamer RTX 4060", "Suporte para RTX 4090", "Capa iPhone 16 Pro") → não reconhece. Teste na Task 2.
2. **Formatos de preço** ("R$ 1.899,90", "R$1.899", "1.899", "De R$ 2.199,00 por R$ 1.899,00", vazio) → valor certo ou `None`, nunca 0. Teste na Task 1.
3. **Loja bloqueando** (403, 429, página de captcha sem a grade de produtos) → `PageBlocked`, erro registrado, outras lojas gravam normal. Testes nas Tasks 5, 7–9 e 10.
4. **Mesmo anúncio aparecendo em dois termos na mesma execução** → uma linha de preço por execução. Teste na Task 3.
5. **Produto esgotado** → não conta como menor preço nem como preço atual. Teste na Task 4.

## File Structure

```
cacador-ofertas/
  pyproject.toml
  catalogo.yaml                 # recorte do Murilo: categorias, termos, padrões
  migracoes/001_inicial.sql
  coletor/
    modelos.py                  # RawOffer, Condition, Match
    precos.py                   # parse_brl
    catalogo.py                 # load_catalog, match_offer
    banco.py                    # gravação (runs, listings, prices, stores, models)
    estatisticas.py             # price_stats
    http.py                     # PoliteClient, FetchError, PageBlocked
    agenda.py                   # categories_due
    lojas/__init__.py           # StoreAdapter, STORES
    lojas/kabum.py | pichau.py | terabyte.py
    capturar.py                 # salva HTML real para virar fixture
    executar.py                 # run_collection, main
  tests/ (test_precos, test_catalogo, test_banco, test_estatisticas, test_http,
          test_agenda, lojas/test_<loja>.py, test_executar) + tests/fixtures/<loja>/*.html
  .github/workflows/capturar.yml, coletar.yml
```

**Limitação do ambiente de quem constrói:** o shell do workspace não alcança os sites das lojas. HTML real é capturado pelo workflow `capturar.yml` rodando no GitHub (o mesmo lugar onde o robô vai rodar, o que já prova que a loja não bloqueia de lá) e baixado com `gh run download`.

---

### Task 1: Projeto base, modelos de dados e leitura de preço

**Files:** Create `pyproject.toml`, `coletor/__init__.py`, `coletor/modelos.py`, `coletor/precos.py`, `tests/test_precos.py`, `.gitignore`

**Interfaces:**
- Produces:
  - `class Condition(StrEnum): NEW = "novo"; USED = "seminovo"`
  - `@dataclass(frozen=True) class RawOffer(store: str, title: str, url: str, price: Decimal | None, cash_price: Decimal | None, in_stock: bool, seller: str | None = None, seller_rating: float | None = None, seller_sales: int | None = None, official_store: bool = False)` com `@property comparable_price -> Decimal | None` (= `cash_price` se houver, senão `price`)
  - `@dataclass(frozen=True) class Match(model_id: str, model_name: str, category: str, condition: Condition, priority: str)`
  - `parse_brl(text: str | None) -> Decimal | None`

- [ ] **Step 1: Criar `pyproject.toml`** (deps: httpx, selectolax, pyyaml, psycopg[binary]; dev: pytest, pytest-postgresql) e instalar com `pip install -e '.[dev]' --break-system-packages`. `git init` se ainda não houver repositório.
- [ ] **Step 2: Teste que falha** em `tests/test_precos.py::test_parse_brl`, parametrizado:

```python
@pytest.mark.parametrize("text,expected", [
    ("R$ 1.899,90", Decimal("1899.90")),
    ("R$1.899", Decimal("1899")),
    ("1.899", Decimal("1899")),
    ("R$ 899,00", Decimal("899.00")),
    ("De R$ 2.199,00 por R$ 1.899,00", Decimal("1899.00")),   # pega o último valor
    ("R$ 12.499,99 à vista", Decimal("12499.99")),
    ("", None), (None, None), ("Indisponível", None), ("R$ 0,00", None),
])
def test_parse_brl(text, expected): assert parse_brl(text) == expected

def test_comparable_price_prefers_cash():
    o = RawOffer("kabum", "x", "u", Decimal("2000"), Decimal("1800"), True)
    assert o.comparable_price == Decimal("1800")
    assert RawOffer("kabum", "x", "u", Decimal("2000"), None, True).comparable_price == Decimal("2000")
```
- [ ] **Step 3:** `pytest tests/test_precos.py -v` → FAIL (import error).
- [ ] **Step 4: Implementar** `modelos.py` e `parse_brl`. Regra: pega o último número no formato brasileiro (ponto = milhar, vírgula = centavos); zero ou nada → `None`.
- [ ] **Step 5:** `pytest tests/test_precos.py -v` → PASS.
- [ ] **Step 6: Commit** `feat: modelos de dados e leitura de preço em reais`

### Task 2: Catálogo e reconhecimento de produtos

**Files:** Create `catalogo.yaml`, `coletor/catalogo.py`, `tests/test_catalogo.py`

**Interfaces:**
- Consumes: `RawOffer`, `Match`, `Condition` (Task 1)
- Produces:
  - `@dataclass Category(id: str, kind: Literal["fixed", "open"], search_terms: list[str], ...)`
  - `@dataclass Catalog(categories: dict[str, Category])` com `terms_for(category_id: str) -> list[str]`
  - `load_catalog(path: Path = Path("catalogo.yaml")) -> Catalog`
  - `match_offer(offer: RawOffer, catalog: Catalog) -> Match | None`
  - `normalize(text: str) -> str` (minúsculas, sem acento, espaços únicos)

Ids de categoria: `gpu`, `iphone`, `cpu`, `placa_mae`, `ram`, `perifericos`, `controles`.

Formato do YAML (o implementador escreve o conteúdo completo a partir da spec §2):
- Categoria `fixed`: `require_any` (termos, ao menos um), `exclude` (termos), `models` em ordem do mais específico para o mais geral; cada modelo tem `id`, `name`, `pattern` (regex sobre o título normalizado), `require` opcional (regex extra), `priority` (`alta`/`baixa`). Primeiro modelo que casar vence.
- `gpu`: RTX 3060 Ti, 3070, 3070 Ti, 3080, 3080 Ti, 3090, 3090 Ti, 4060, 4060 Ti 8GB, 4060 Ti 16GB, 4070, 4070 Super, 4070 Ti, 4070 Ti Super, 4080, 4080 Super, 4090, 5050, 5060, 5060 Ti 8GB, 5060 Ti 16GB, 5070, 5070 Ti, 5080, 5090. Variante de memória sem "8GB"/"16GB" no título → não reconhece. Termos de busca amplos (ex.: `rtx 4070` cobre Super e Ti) para manter a execução curta.
- `iphone`: gerações 15 em diante e variantes (base, Plus, Pro, Pro Max, e, Air — conferir a linha atual da Apple antes de escrever). Pro e Pro Max `priority: alta`, demais `baixa`. `storage_required: true`: capacidade lida do título (`128gb|256gb|512gb|1tb`) entra no id (`iphone-16-pro-max-256gb`); sem capacidade → não reconhece. Palavras de seminovo (`seminovo`, `usado`, `recondicionado`, `vitrine`, `grade a`, `refurbished`) → `Condition.USED` e sufixo `-seminovo` no id e "(seminovo)" no nome.
- `controles`: DualSense, DualSense Edge, Controle Xbox Series (Microsoft). Exigir marca original (`sony`/`dualsense`; `microsoft`/`xbox wireless`). Excluir `compativel`, `generico`, `tipo`, `similar`, `capa`, `case`, `suporte`, `base carregadora`, `dock`, `grip`, `pelicula`.
- Categoria `open` (`cpu`, `placa_mae`, `ram`, `perifericos`): `require_all` = lista de grupos, cada grupo "pelo menos um termo". `id` = `<categoria>:<slug do título normalizado, até 80 caracteres>`; `name` = título original; `priority: baixa`. cpu: (intel|amd) e (core i3/i5/i7/i9|core ultra|ryzen). placa_mae: (placa mae|motherboard) e (asus|gigabyte). ram: (memoria) e (ddr4|ddr5), excluir notebook/sodimm. perifericos: (corsair|logitech) e (headset|fone|teclado|mouse), excluir mousepad/mouse pad.
- Exclusões globais (todas as categorias): `notebook`, `laptop`, `pc gamer`, `computador`, `kit upgrade`, `capa`, `pelicula`, `suporte`, `cabo`, `adesivo`.
- Seminovo fora de `iphone` → `None`.

- [ ] **Step 1: Testes que falham** em `tests/test_catalogo.py` (usa o `catalogo.yaml` real):

```python
CASES = [
    ("Placa de Vídeo Gigabyte GeForce RTX 4070 Ti SUPER Gaming OC 16GB", "rtx-4070-ti-super"),
    ("Placa de Vídeo ASUS TUF RTX 4070 Super 12GB GDDR6X", "rtx-4070-super"),
    ("Placa de Vídeo MSI RTX 4060 Ti Ventus 2X 16GB", "rtx-4060-ti-16gb"),
    ("Placa de Vídeo MSI RTX 4060 Ti Ventus 2X", None),              # sem memória
    ("Placa de Vídeo Galax RTX 3060 12GB", None),                    # abaixo do recorte
    ("Placa de Vídeo Zotac RTX 3060 Ti Twin Edge 8GB", "rtx-3060-ti"),
    ("Notebook Gamer Acer Nitro RTX 4070 i7", None),
    ("PC Gamer Completo RTX 4060 Ryzen 5", None),
    ("Suporte para Placa de Vídeo RTX 4090", None),
    ("Apple iPhone 16 Pro Max 256GB Titânio-deserto", "iphone-16-pro-max-256gb"),
    ("iPhone 15 Pro 128GB Seminovo Grade A", "iphone-15-pro-128gb-seminovo"),
    ("Capa iPhone 16 Pro Silicone", None),
    ("iPhone 14 Pro 128GB", None),                                   # abaixo do recorte
    ("Controle Sony DualSense Edge PS5", "dualsense-edge"),
    ("Controle Compatível PS5 Sem Fio Tipo DualSense", None),
    ("Placa de Vídeo RTX 4070 12GB Usada", None),                    # seminovo fora de iPhone
]
@pytest.mark.parametrize("title,expected", CASES)
def test_match_fixed(title, expected): ...  # match_offer(RawOffer("kabum", title, "u", D("1"), None, True), cat); compara model_id ou None

def test_open_category_ids():
    m = match_offer(offer("Processador AMD Ryzen 7 7800X3D AM5"), cat)
    assert m.category == "cpu" and m.model_id.startswith("cpu:")
    assert match_offer(offer("Processador Intel Core i5-14600K LGA1700"), cat).category == "cpu"
    assert match_offer(offer("Placa Mãe MSI B650 Tomahawk"), cat) is None
    assert match_offer(offer("Memória Kingston Fury 16GB DDR5 Notebook SODIMM"), cat) is None
    assert match_offer(offer("Mousepad Logitech G640"), cat) is None
    assert match_offer(offer("Headset Gamer Corsair HS80 RGB"), cat).category == "perifericos"
```
*(O formato exato do slug das categorias abertas fica com o implementador.)*
- [ ] **Step 2:** `pytest tests/test_catalogo.py -v` → FAIL.
- [ ] **Step 3: Escrever `catalogo.yaml` e implementar `catalogo.py`.**
- [ ] **Step 4:** `pytest tests/test_catalogo.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: catálogo do recorte e reconhecimento de produtos`

### Task 3: Banco de dados e gravação

**Files:** Create `migracoes/001_inicial.sql`, `coletor/banco.py`, `tests/conftest.py`, `tests/test_banco.py`

**Interfaces:**
- Consumes: `RawOffer`, `Match` (Task 1)
- Produces:
  - Tabelas: `stores(id text pk, name text, last_success_at timestamptz, last_error text, last_error_at timestamptz)`; `models(id text pk, category text, name text, condition text, priority text)`; `runs(id bigserial pk, started_at, finished_at, summary jsonb)`; `listings(id bigserial pk, store_id text refs stores, url text unique, title text, model_id text null refs models, category text null, seller text, seller_rating real, seller_sales int, official_store bool, first_seen_at, last_seen_at)`; `prices(listing_id bigint refs listings, run_id bigint refs runs, collected_at timestamptz, price numeric(12,2), cash_price numeric(12,2), comparable_price numeric(12,2) not null, in_stock bool, primary key (listing_id, run_id))`; índice `prices(collected_at)`.
  - `apply_migrations(conn) -> None` (executa `migracoes/*.sql` em ordem; idempotente com `create ... if not exists`)
  - `start_run(conn, started_at: datetime) -> int`
  - `save_offers(conn, run_id: int, store_id: str, items: list[tuple[RawOffer, Match | None]], seen_at: datetime) -> int` — uma transação; upsert de `models` (quando houver match), upsert de `listings` por `url` (atualiza `title`, `model_id`, `last_seen_at`), insert em `prices` com `ON CONFLICT DO NOTHING`; oferta sem `comparable_price` não gera linha de preço. Retorna quantas linhas de preço gravou.
  - `record_store_result(conn, store_id: str, name: str, ok: bool, error: str | None, at: datetime) -> None` — sucesso atualiza `last_success_at` e limpa `last_error`.
  - `finish_run(conn, run_id: int, finished_at: datetime, summary: dict) -> None`

- [ ] **Step 1: `tests/conftest.py`** com fixture `conn` via `pytest_postgresql.factories` (executável `/usr/lib/postgresql/16/bin/pg_ctl`; no CI, `postgresql_proc` encontra o binário pelo PATH) que roda `apply_migrations`.
- [ ] **Step 2: Testes que falham:**

```python
def test_same_listing_twice_in_run_gives_one_price(conn):
    run = start_run(conn, T0)
    item = (RawOffer("kabum", "RTX 4070 12GB", "https://k/1", D("4000"), D("3800"), True), MATCH_4070)
    assert save_offers(conn, run, "kabum", [item, item], T0) == 1
    assert count(conn, "prices") == 1 and count(conn, "listings") == 1

def test_offer_without_price_keeps_listing_no_price(conn): ...   # listing 1, prices 0
def test_unmatched_listing_has_null_model(conn): ...             # model_id is None, models vazio
def test_store_error_then_success_clears_error(conn): ...        # last_error preenchido, depois None e last_success_at = T1
def test_apply_migrations_twice_is_safe(conn): apply_migrations(conn)
```
- [ ] **Step 3:** `pytest tests/test_banco.py -v` → FAIL.
- [ ] **Step 4: Implementar** a migração e `banco.py`.
- [ ] **Step 5:** `pytest tests/test_banco.py -v` → PASS.
- [ ] **Step 6: Commit** `feat: esquema do banco e gravação das coletas`

### Task 4: Estatísticas de preço

**Files:** Create `coletor/estatisticas.py`, `tests/test_estatisticas.py`

**Interfaces:**
- Consumes: tabelas da Task 3
- Produces:
  - `@dataclass(frozen=True) class PriceStats(model_id: str, current_best: Decimal | None, current_store: str | None, current_url: str | None, avg_30d: Decimal | None, min_90d: Decimal | None, change_1d_pct: float | None, history_days: int)`
  - `price_stats(conn, model_id: str, now: datetime) -> PriceStats`

Definições (os planos 2 e 3 dependem delas):
- Só entram preços com `in_stock = true`.
- **Atual:** menor `comparable_price` entre preços coletados nas últimas 6 h, com loja e URL dele.
- **Mínimo do dia:** menor preço do dia no fuso `America/Sao_Paulo`.
- **avg_30d:** média dos mínimos diários dos 30 dias anteriores a hoje (hoje fora). **min_90d:** menor mínimo diário dos 90 dias anteriores a hoje. **change_1d_pct:** `(atual − mínimo de ontem) / mínimo de ontem × 100`, arredondado a 1 casa.
- **history_days:** dias distintos com dado, sem contar hoje. O plano 3 só usa os critérios 2 e 3 de alerta com `history_days >= 7` *(chamada minha)*.

- [ ] **Step 1: Testes que falham** (inserem preços direto com datas controladas; `now = 2026-11-18 15:00 -03:00`):

```python
def test_out_of_stock_ignored(conn):       # esgotado a R$ 100 não vira atual nem min_90d
def test_daily_min_uses_sao_paulo_day(conn):  # preço às 01:30 UTC de 18/11 conta como 17/11
def test_stats_basic(conn):
    # dias 2..31 antes: 4000; ontem: 3900; agora: 3510 (kabum) e 3600 (pichau)
    s = price_stats(conn, "rtx-4070", NOW)
    assert s.current_best == D("3510") and s.current_store == "kabum"
    assert s.avg_30d == D("3996.67")          # (3900 + 29 × 4000) / 30, 2 casas
    assert s.min_90d == D("3900") and s.change_1d_pct == -10.0 and s.history_days == 31
def test_no_data(conn):                    # tudo None, history_days == 0
def test_stale_price_not_current(conn):    # preço de 7 h atrás → current_best None
```
- [ ] **Step 2:** `pytest tests/test_estatisticas.py -v` → FAIL.
- [ ] **Step 3: Implementar** com uma consulta SQL usando `date_trunc('day', collected_at at time zone 'America/Sao_Paulo')`.
- [ ] **Step 4:** `pytest tests/test_estatisticas.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: estatísticas de preço (atual, média 30d, mínimo 90d)`

### Task 5: Cliente HTTP educado e agenda

**Files:** Create `coletor/http.py`, `coletor/agenda.py`, `tests/test_http.py`, `tests/test_agenda.py`

**Interfaces:**
- Produces:
  - `class FetchError(Exception)`; `class PageBlocked(FetchError)`
  - `class PoliteClient(min_interval_s: float = 3.0, timeout_s: float = 20.0, retries: int = 2, transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic)` com `get(url: str) -> str`. Cabeçalhos de navegador comum (`User-Agent`, `Accept-Language: pt-BR`). 403/429 → `PageBlocked` sem nova tentativa; 5xx e timeout → tenta de novo até `retries`, depois `FetchError`.
  - `FAST = ("gpu", "iphone")`; `SLOW = ("cpu", "placa_mae", "ram", "perifericos", "controles")`
  - `categories_due(now: datetime) -> list[str]` — sempre `FAST`; `SLOW` quando a hora em `America/Sao_Paulo` for múltipla de 3.

- [ ] **Step 1: Testes que falham** (`httpx.MockTransport`, `sleep` e `clock` falsos):

```python
def test_waits_min_interval_between_calls(): ...   # 2 gets seguidos → sleep chamado com ~3.0
def test_403_raises_page_blocked_without_retry(): ...  # 1 requisição só
def test_500_retries_then_fetch_error(): ...       # 3 requisições, depois FetchError
def test_categories_due():
    assert categories_due(dt("2026-11-18 10:05", SP)) == ["gpu", "iphone"]
    assert set(categories_due(dt("2026-11-18 09:05", SP))) == set(FAST + SLOW)
```
- [ ] **Step 2:** `pytest tests/test_http.py tests/test_agenda.py -v` → FAIL.
- [ ] **Step 3: Implementar** `http.py` e `agenda.py`.
- [ ] **Step 4:** mesmos testes → PASS.
- [ ] **Step 5: Commit** `feat: cliente http com intervalo entre requisições e agenda por categoria`

### Task 6: Repositório no GitHub e captura de páginas reais

*Depende do Murilo: criar conta no GitHub (se não tiver) e um repositório **público** vazio `cacador-ofertas`. O implementador dá o passo a passo em linguagem simples e, com o repositório criado, anexa com `add_repo` (acesso `push`) e envia os commits.*

**Files:** Create `coletor/lojas/__init__.py`, `coletor/capturar.py`, `.github/workflows/capturar.yml`

**Interfaces:**
- Consumes: `PoliteClient` (Task 5), `Catalog.terms_for` (Task 2)
- Produces:
  - `class StoreAdapter(Protocol)`: `id: str`, `name: str`, `search_urls(term: str) -> list[str]` (até 2 páginas), `parse_search(html: str, url: str) -> list[RawOffer]`. Contrato: página sem resultados reconhecida → `[]`; página sem a estrutura de produtos (captcha, bloqueio, layout desconhecido) → `PageBlocked`.
  - `STORES: dict[str, StoreAdapter]` (preenchido nas Tasks 7–9)
  - `python -m coletor.capturar --store <id> --term "<termo>" [--out capturas/]` salva o HTML de cada URL de busca
  - Workflow `capturar.yml` (`workflow_dispatch` com entradas `store` e `term`) que roda a captura e sobe `capturas/` como artifact

- [ ] **Step 1:** Implementar `capturar.py` usando um mapa provisório `SEARCH_URLS = {"kabum": ..., "pichau": ..., "terabyte": ...}` (formato de URL de busca de cada loja, conferido abrindo a loja pelo navegador do app ou WebFetch) e o workflow.
- [ ] **Step 2:** Push. Rodar `gh workflow run capturar.yml -f store=kabum -f term="rtx 4070"` (e o mesmo para pichau e terabyte; mais um termo de iPhone e um de categoria lenta por loja).
- [ ] **Step 3: Verificar:** `gh run download <id>` traz HTML com produtos visíveis (procurar um preço `R$` no arquivo). Se vier vazio porque a loja monta a página por JavaScript, anotar a loja como `needs_browser` para a task dela. Se vier 403/captcha, avisar o Murilo antes de seguir: aquela loja não entra pela nuvem.
- [ ] **Step 4:** Copiar os HTMLs para `tests/fixtures/<loja>/`. Commit `chore: captura de páginas reais das lojas`.

### Tasks 7, 8 e 9: Adaptadores Kabum, Pichau e Terabyte

Uma task por loja, mesma estrutura. Revisor pode aprovar uma e rejeitar outra.

**Files (por loja `<id>`):** Create `coletor/lojas/<id>.py`, `tests/lojas/test_<id>.py`; Modify `coletor/lojas/__init__.py` (registrar em `STORES`)

**Interfaces:**
- Consumes: `StoreAdapter`, `PageBlocked`, `RawOffer`, `parse_brl`, fixtures da Task 6
- Produces: `class <Loja>Adapter` com `id = "kabum" | "pichau" | "terabyte"` e `name = "Kabum" | "Pichau" | "Terabyte"`

- [ ] **Step 1: Testes que falham** contra as fixtures reais:

```python
def test_parses_products():
    offers = Adapter().parse_search(fixture("busca_rtx_4070.html"), URL)
    assert len(offers) >= 5
    o = offers[0]
    assert o.store == "<id>" and o.url.startswith("https://") and "4070" in o.title.lower()
    assert o.comparable_price and o.comparable_price > 100
    # valores exatos do primeiro produto copiados da fixture, à mão:
    assert (o.title, o.price, o.cash_price, o.in_stock) == (TITLE_0, PRICE_0, CASH_0, True)
def test_out_of_stock_flagged(): ...       # item esgotado da fixture → in_stock False (se a fixture tiver um)
def test_captcha_page_raises(): pytest.raises(PageBlocked, Adapter().parse_search, "<html><body>Verifique se você é humano</body></html>", URL)
def test_search_urls_two_pages(): assert len(Adapter().search_urls("rtx 4070")) == 2
```
- [ ] **Step 2:** `pytest tests/lojas/test_<id>.py -v` → FAIL.
- [ ] **Step 3: Implementar o adaptador.** Preferir JSON embutido na página (ex.: `__NEXT_DATA__`, `application/ld+json`) a seletores CSS, porque quebra menos quando a loja muda o visual. Se a Task 6 marcou `needs_browser`, adicionar `needs_browser = True` ao adaptador e um `BrowserClient.get(url) -> str` (Playwright, Chromium) em `http.py` com o mesmo intervalo de 3 s; instalar o Chromium no workflow.
- [ ] **Step 4:** `pytest tests/lojas/test_<id>.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: adaptador <Loja>`

### Task 10: Orquestrador e agendamento

**Files:** Create `coletor/executar.py`, `tests/test_executar.py`, `.github/workflows/coletar.yml`

**Interfaces:**
- Consumes: `categories_due`, `Catalog`, `match_offer`, `STORES`, `PoliteClient`, `start_run`, `save_offers`, `record_store_result`, `finish_run`
- Produces:
  - `@dataclass class RunSummary(run_id: int, offers_seen: int, matched: int, unmatched: int, prices_saved: int, store_errors: dict[str, str])`
  - `run_collection(conn, stores: dict[str, StoreAdapter], catalog: Catalog, make_client: Callable[[StoreAdapter], PoliteClient], now: datetime) -> RunSummary` — uma thread por loja busca todos os termos das categorias devidas; a thread principal grava. Erro em qualquer página de uma loja → para aquela loja, registra `record_store_result(ok=False, error="<tipo>: <mensagem em português>")` e descarta só o que aquela loja coletou nesta execução. Loja com tudo certo → `ok=True`.
  - `main() -> int` — lê `DATABASE_URL`, aplica migrações, roda, imprime o resumo; retorna 0 se ao menos uma loja funcionou, 1 se todas falharam.
  - `coletar.yml`: `schedule: cron "7 * * * *"` + `workflow_dispatch`, Python 3.12, `pip install .`, `python -m coletor.executar`, `DATABASE_URL` de `secrets`, `concurrency: coletar` (não sobrepor execuções), `timeout-minutes: 20`. Job extra mensal que reativa o próprio workflow via API (`gh workflow enable coletar.yml`), porque o GitHub desliga agendamentos de repositório público após 60 dias sem atividade; conferir na documentação atual do GitHub se isso reinicia o prazo e, se não, usar a forma que a documentação indicar.

- [ ] **Step 1: Testes que falham** com adaptadores falsos e banco de teste:

```python
def test_one_store_blocked_others_saved(conn):
    s = run_collection(conn, {"a": FakeOk("a"), "b": FakeBlocked("b")}, CATALOG, fake_client, NOW_SLOW_HOUR)
    assert "b" in s.store_errors and s.prices_saved > 0
    assert store_row(conn, "b").last_error and store_row(conn, "a").last_error is None
def test_unmatched_counted(conn): ...      # FakeOk devolve 1 reconhecido + 1 "Capa iPhone" → matched 1, unmatched 1
def test_only_fast_categories_off_hour(conn): ...  # termos pedidos ao FakeOk ⊆ termos de gpu+iphone
def test_main_returns_1_when_all_fail(monkeypatch, conn): ...
```
- [ ] **Step 2:** `pytest tests/test_executar.py -v` → FAIL.
- [ ] **Step 3: Implementar** `executar.py` e `coletar.yml`.
- [ ] **Step 4:** `pytest -v` (suíte inteira) → PASS.
- [ ] **Step 5: Commit** `feat: orquestrador da coleta e agendamento de hora em hora`

### Task 11: Ligar no Supabase e primeira coleta real

*Depende do Murilo: aprovar a criação do projeto no Supabase (plano grátis) e colar um segredo no GitHub, com passo a passo guiado.*

**Files:** nenhum código novo; Modify `README.md` (o que é, como ver se está funcionando, em português simples)

- [ ] **Step 1:** Criar o projeto `cacador-ofertas` pelo conector do Supabase (`get_cost` → `confirm_cost` precisa dar US$ 0; região São Paulo `sa-east-1`) e aplicar `migracoes/001_inicial.sql` com `apply_migration`. Ativar RLS em todas as tabelas sem políticas públicas (o robô usa a conexão direta; o site do plano 2 define o acesso de leitura).
- [ ] **Step 2:** Guiar o Murilo a copiar a connection string (pooler, modo session) e salvar como secret `DATABASE_URL` no repositório.
- [ ] **Step 3:** `gh workflow run coletar.yml`; aguardar; `gh run view --log` mostra o resumo com `prices_saved > 0` e sem erro em pelo menos uma loja.
- [ ] **Step 4: Verificar no banco** (`execute_sql`): `select store_id, count(*) from listings group by 1;` (as três lojas com linhas), `select count(*) from listings where model_id is null;` (anotar a taxa de não reconhecidos; acima de 40% numa loja → revisar o catálogo antes de fechar) e `select * from stores;` (sem `last_error`).
- [ ] **Step 5:** Commit do README. Contar ao Murilo, em linguagem simples, o que já está rodando e quais lojas funcionaram.
