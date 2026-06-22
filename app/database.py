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

CREATE INDEX IF NOT EXISTS idx_signals_inst ON signals (instrument, id);
CREATE INDEX IF NOT EXISTS idx_trades_inst  ON paper_trades (instrument, id);
"""


def get_conn() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _migrate(conn) -> None:
    """Ajoute les colonnes manquantes sur une base préexistante."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(paper_trades)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN source TEXT DEFAULT 'auto'")


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    conn.close()
