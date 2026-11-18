-- Esquema inicial do Caçador de Ofertas.
create table if not exists stores (
    id               text primary key,
    name             text not null,
    last_success_at  timestamptz,
    last_error       text,
    last_error_at    timestamptz
);

create table if not exists models (
    id         text primary key,
    category   text not null,
    name       text not null,
    condition  text not null,
    priority   text not null
);

create table if not exists runs (
    id           bigserial primary key,
    started_at   timestamptz not null,
    finished_at  timestamptz,
    summary      jsonb
);

create table if not exists listings (
    id              bigserial primary key,
    store_id        text not null references stores(id),
    url             text not null unique,
    title           text not null,
    model_id        text references models(id),
    category        text,
    seller          text,
    seller_rating   real,
    seller_sales    integer,
    official_store  boolean not null default false,
    first_seen_at   timestamptz not null,
    last_seen_at    timestamptz not null
);
create index if not exists listings_model_idx on listings(model_id);

create table if not exists prices (
    listing_id        bigint not null references listings(id) on delete cascade,
    run_id            bigint not null references runs(id) on delete cascade,
    collected_at      timestamptz not null,
    price             numeric(12,2),
    cash_price        numeric(12,2),
    comparable_price  numeric(12,2) not null,
    in_stock          boolean not null,
    primary key (listing_id, run_id)
);
create index if not exists prices_collected_idx on prices(collected_at);
