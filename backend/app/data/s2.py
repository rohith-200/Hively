"""OWNER: Suman. SingleStore plumbing: one shared connection, schema, embeddings.
Only store.py, audit.py and scripts/seed_data.py import this."""
import json
import os
import threading
import time
from datetime import datetime, timezone

VECTOR_DIM = 384
EMBED_MODEL = "BAAI/bge-small-en-v1.5"      # normalized, so dot product = cosine

SCHEMA = [
    f"""CREATE TABLE IF NOT EXISTS products (
        id VARCHAR(64) PRIMARY KEY, store VARCHAR(16), store_product_id VARCHAR(64),
        name TEXT, room VARCHAR(32), category VARCHAR(64), style VARCHAR(64),
        colors JSON, material TEXT, price_usd DOUBLE, image_url TEXT, url TEXT,
        in_stock BOOL, description TEXT,
        vec VECTOR({VECTOR_DIM}) NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS runs (
        id VARCHAR(32) PRIMARY KEY, user_id VARCHAR(64), state VARCHAR(24),
        budget_usd DOUBLE, run_json JSON, created_at DATETIME, updated_at DATETIME)""",
    """CREATE TABLE IF NOT EXISTS audit_events (
        run_id VARCHAR(32), seq INT, ts DATETIME(6), actor VARCHAR(16), action VARCHAR(64),
        summary TEXT, data JSON, prev_hash CHAR(64), hash CHAR(64),
        PRIMARY KEY (run_id, seq))""",
    """CREATE TABLE IF NOT EXISTS merchant_orders (
        run_id VARCHAR(32), store VARCHAR(16), mode VARCHAR(16), status VARCHAR(16),
        order_id VARCHAR(64), url TEXT, amount_usd DOUBLE, item_ids JSON, error TEXT,
        PRIMARY KEY (run_id, store))""",
]

DOWN_SECONDS = 30      # after a failed statement, skip SingleStore this long so callers fall back fast

_lock = threading.RLock()
_conn = None
_model = None
_down_until = 0.0


def url() -> str:
    return os.getenv("SINGLESTORE_URL", "").strip()


def _connect():
    import singlestoredb
    return singlestoredb.connect(url(), autocommit=True, connect_timeout=8)


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Run one statement on the shared connection; reconnect once if it has gone stale."""
    global _conn, _down_until
    with _lock:
        if time.monotonic() < _down_until:
            raise RuntimeError("SingleStore marked down; retrying shortly")
        if not url():
            raise RuntimeError("SINGLESTORE_URL is not set")
        for attempt in (1, 2):
            try:
                if _conn is None:
                    _conn = _connect()
                with _conn.cursor() as cur:
                    cur.execute(sql, params)
                    if not cur.description:
                        return []
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
            except Exception:
                try:
                    if _conn is not None:
                        _conn.close()
                except Exception:
                    pass
                _conn = None
                if attempt == 2:
                    _down_until = time.monotonic() + DOWN_SECONDS
                    raise
    return []


def create_tables() -> None:
    for ddl in SCHEMA:
        query(ddl)


def embed(texts: list[str]) -> list[list[float]]:
    """384-dim vectors. Same model for products and queries. First call loads the model."""
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding
            _model = TextEmbedding(EMBED_MODEL)
        return [v.tolist() for v in _model.embed(texts)]


def vec_param(v: list[float]) -> str:
    return json.dumps(v)


def as_json(v):
    """JSON columns come back parsed or as text depending on the driver; accept both."""
    if isinstance(v, (bytes, bytearray)):
        v = v.decode()
    return json.loads(v) if isinstance(v, str) else v


def to_db_time(ts: datetime) -> datetime:
    return ts.astimezone(timezone.utc).replace(tzinfo=None)


def from_db_time(ts: datetime) -> datetime:
    return ts.replace(tzinfo=timezone.utc)


def upsert_products(rows: list[tuple]) -> int:
    """Embed and REPLACE products. rows = [(Product, description), ...]."""
    if not rows:
        return 0
    create_tables()
    vecs = embed([f"{p.name}. {p.category}, {p.style}, {p.room}. Colors: {', '.join(p.colors)}. "
                  f"Material: {p.material}. {desc}" for p, desc in rows])
    for (p, desc), v in zip(rows, vecs):
        query("REPLACE INTO products (id, store, store_product_id, name, room, category, style, colors, "
              "material, price_usd, image_url, url, in_stock, description, vec) "
              "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
              (p.id, p.store, p.store_product_id, p.name, p.room, p.category, p.style,
               json.dumps(p.colors), p.material, p.price_usd, p.image_url, p.url,
               1 if p.in_stock else 0, desc, vec_param(v)))
    return len(rows)
