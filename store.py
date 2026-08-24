# Пары YouTrack ↔ Bitrix. Истина связи здесь, не в чате.

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pairs (
    youtrack_id TEXT PRIMARY KEY,
    bitrix_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    project_key TEXT NOT NULL
);
"""


class PairStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def ping(self) -> None:
        with self._conn() as conn:
            conn.execute("SELECT 1").fetchone()

    def get_by_youtrack(self, youtrack_id: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM pairs WHERE youtrack_id = ?", (youtrack_id,)
            ).fetchone()

    def get_by_bitrix(self, bitrix_id: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM pairs WHERE bitrix_id = ?", (str(bitrix_id),)
            ).fetchone()

    def put(self, youtrack_id: str, bitrix_id: str, source: str, project_key: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO pairs (youtrack_id, bitrix_id, source, project_key)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(youtrack_id) DO UPDATE SET
                    bitrix_id = excluded.bitrix_id,
                    source = excluded.source,
                    project_key = excluded.project_key
                """,
                (youtrack_id, str(bitrix_id), source, project_key),
            )
            conn.commit()
