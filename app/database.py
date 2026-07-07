"""
Accès SQLite. Un seul processus possède la base (collector + trader + analyste
+ web dans le même conteneur). Mode WAL pour la concurrence entre threads.

Schéma multi-actifs : chaque table porte une colonne `instrument`.
"""
import os
import sqlite3

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    instrument  TEXT NOT NULL,
    timestamp   INTEGER NOT NULL,
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL NOT NULL,
    PRIMARY KEY (instrument, timestamp)
);

CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument  TEXT NOT NULL,
    timestamp   INTEGER NOT NULL,
    signal      TEXT NOT NULL,
    price       REAL NOT NULL,
    score       REAL,
    details     TEXT
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument  TEXT NOT NULL,
    timestamp   INTEGER NOT NULL,
    action      TEXT NOT NULL,
    price       REAL NOT NULL,
    balance     REAL NOT NULL,
    position    REAL NOT NULL,
    source      TEXT DEFAULT 'auto'
);

CREATE TABLE IF NOT EXISTS ai_analysis (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument  TEXT NOT NULL,
    timestamp   INTEGER NOT NULL,
    score       REAL,
    sentiment   TEXT,
    reasoning   TEXT,
    headlines   TEXT
);

CREATE TABLE IF NOT EXISTS adventure_trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    adventure_id  TEXT NOT NULL,
    instrument    TEXT NOT NULL,
    timestamp     INTEGER NOT NULL,
    action        TEXT NOT NULL,
    price         REAL NOT NULL,
    balance       REAL NOT NULL,
    position      REAL NOT NULL,
    source        TEXT DEFAULT 'auto'
);

CREATE TABLE IF NOT EXISTS ml_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument   TEXT NOT NULL,
    timestamp    INTEGER NOT NULL,
    model_type   TEXT,
    n_samples    INTEGER,
    accuracy     REAL,
    baseline     REAL,
    proba_up     REAL,
    loss_curve   TEXT,
    note         TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_inst ON signals (instrument, id);
CREATE INDEX IF NOT EXISTS idx_trades_inst  ON paper_trades (instrument, id);
CREATE INDEX IF NOT EXISTS idx_advtrades    ON adventure_trades (adventure_id, instrument, id);
CREATE INDEX IF NOT EXISTS idx_mlruns_inst  ON ml_runs (instrument, id);
"""


def get_conn() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL est persistant (en-tête du fichier, posé par init_db) → inutile de le re-poser.
    # Réglages légers pour Raspberry Pi / carte SD : moins de fsync, cache et temp bornés.
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-2000")  # ~2 Mo par connexion
    return conn


def _migrate(conn) -> None:
    """Ajoute les colonnes manquantes sur une base préexistante."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(paper_trades)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN source TEXT DEFAULT 'auto'")


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute("PRAGMA journal_mode=WAL")  # posé une fois, persistant
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
