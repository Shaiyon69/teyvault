import datetime
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS wishes (
    id TEXT PRIMARY KEY,
    uid TEXT NOT NULL,
    gacha_type TEXT NOT NULL,
    item_type TEXT,
    name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    time TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS wishes_uid_type ON wishes (uid, gacha_type);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS achievements_done (id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS primogems (time TEXT NOT NULL, uid TEXT NOT NULL, count INTEGER NOT NULL);
INSERT OR IGNORE INTO meta VALUES ('schema_version', '1');
"""

COLUMNS = ("id", "uid", "gacha_type", "item_type", "name", "rank", "time")


def default_path() -> Path:
    if env := os.environ.get("TEYVAT_DB"):
        return Path(env)
    if os.name == "nt":  # CLI and desktop GUI share one DB
        root = Path(os.environ["APPDATA"])
        base, olds = root / "Teyvault", [root / "TeyLogs", root / "TeyvatAuditor"]
    elif app_dir := os.environ.get("FLET_APP_STORAGE_DATA"):  # set inside Android/iOS app builds
        base, olds = Path(app_dir), []
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        base, olds = root / "teyvault", [root / "teylogs", root / "teyvat-auditor"]
    old = next((o for o in olds if o.exists()), None)
    if old and not base.exists():  # carry data over from an earlier app name
        old.rename(base)
    return base / "teyvat.db"


def connect(path=None) -> sqlite3.Connection:
    path = path or default_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_wishes(conn, rows) -> int:
    """Insert wish dicts (keys = COLUMNS); duplicates by id are ignored. Returns rows added."""
    before = conn.total_changes
    with conn:
        conn.executemany(
            f"INSERT OR IGNORE INTO wishes VALUES ({','.join('?' * len(COLUMNS))})",
            ([r[c] for c in COLUMNS] for r in rows),
        )
    return conn.total_changes - before


def has_wish(conn, wish_id) -> bool:
    return conn.execute("SELECT 1 FROM wishes WHERE id = ?", (wish_id,)).fetchone() is not None


def uids(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT uid FROM wishes ORDER BY uid")]


def wishes(conn, uid) -> list[dict]:
    # Wish ids are monotonically increasing, so sorting by id gives pull order.
    rows = conn.execute(
        "SELECT * FROM wishes WHERE uid = ? ORDER BY CAST(id AS INTEGER)", (uid,)
    )
    return [dict(r) for r in rows]


def count_wishes(conn, uid) -> int:
    return conn.execute("SELECT COUNT(*) FROM wishes WHERE uid = ?", (uid,)).fetchone()[0]


def done_ids(conn) -> set[int]:
    return {r[0] for r in conn.execute("SELECT id FROM achievements_done")}


def set_done(conn, achievement_id, done: bool) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO achievements_done VALUES (?)" if done
                     else "DELETE FROM achievements_done WHERE id = ?", (achievement_id,))


def log_primogems(conn, uid, count: int) -> None:
    """Primogem count the user typed in (no API exposes it); the log is their ledger."""
    with conn:
        conn.execute("INSERT INTO primogems VALUES (?, ?, ?)",
                     (datetime.datetime.now().isoformat(timespec="seconds"), uid, count))


def primogem_log(conn, uid, limit=6) -> list[dict]:
    """Newest first."""
    rows = conn.execute("SELECT * FROM primogems WHERE uid = ? ORDER BY time DESC, rowid DESC LIMIT ?",
                        (uid, limit))
    return [dict(r) for r in rows]


def delete_wishes(conn, uid) -> int:
    with conn:
        return conn.execute("DELETE FROM wishes WHERE uid = ?", (uid,)).rowcount


def drop_covered_synthetic(conn) -> int:
    """Delete synthetic-id rows (imports without real ids, < 19 digits) that real API rows of the
    same uid and pity pool also cover, i.e. at or after the oldest real pull. Avoids double counts."""
    pool = "CASE {}.gacha_type WHEN '400' THEN '301' ELSE {}.gacha_type END"
    with conn:
        cur = conn.execute(f"""
            DELETE FROM wishes AS s WHERE length(s.id) < 19 AND EXISTS (
                SELECT 1 FROM wishes AS r WHERE length(r.id) >= 19 AND r.uid = s.uid
                AND {pool.format('r', 'r')} = {pool.format('s', 's')} AND r.time <= s.time)""")
    return cur.rowcount


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(conn, key, value) -> None:
    with conn:
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
