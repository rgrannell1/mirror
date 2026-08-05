"""D1 cache database and social card storage."""

import sqlite3
from typing import Optional

from mirror.commons.config import D1_DUMP_PATH
from mirror.commons.tables import SOCIAL_CARD_TABLE


class SocialCardTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(SOCIAL_CARD_TABLE)

    def add(
        self, path: str, description: Optional[str], title: Optional[str], image_url: str
    ) -> None:
        self.conn.execute(
            "insert or replace into social_cards"
            " (path, description, title, image_url) values (?, ?, ?, ?)",
            (path, description, title, image_url),
        )
        self.conn.commit()


class D1SqliteDatabase:
    """A SQLite database used just for D1 caching"""

    conn: sqlite3.Connection

    def __init__(self, fpath: str) -> None:
        self.conn = sqlite3.connect(fpath)

    def social_card_table(self):
        return SocialCardTable(self.conn)

    def dump(self):
        """Write an idempotent SQL dump: safe to re-run, and safe against the
        partial-apply retries wrangler's remote D1 import performs."""
        with open(D1_DUMP_PATH, "w", encoding="utf-8") as f:
            f.write("DROP TABLE IF EXISTS social_cards;\n")
            for line in self.conn.iterdump():
                if "social_cards" not in line:
                    continue

                if line.startswith("CREATE TABLE"):
                    line = line.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
                if line.startswith("INSERT INTO"):
                    line = line.replace("INSERT INTO", "INSERT OR REPLACE INTO", 1)

                f.write(line + "\n")

        self.conn.close()
