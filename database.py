import sqlite3
import os
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "members.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS verified_members (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         TEXT NOT NULL,
                guild_id        TEXT NOT NULL,
                username        TEXT,
                access_token    TEXT NOT NULL,
                refresh_token   TEXT NOT NULL,
                expires_at      REAL NOT NULL,
                verified_at     REAL NOT NULL,
                UNIQUE(user_id, guild_id)
            )
        """)
        self.conn.commit()

    # ── Save / Update ────────────────────────────────────────
    def save_member(
        self,
        user_id: str,
        guild_id: str,
        username: str,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        verified_at: float,
    ):
        self.conn.execute("""
            INSERT INTO verified_members
                (user_id, guild_id, username, access_token, refresh_token, expires_at, verified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                username      = excluded.username,
                access_token  = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at    = excluded.expires_at,
                verified_at   = excluded.verified_at
        """, (user_id, guild_id, username, access_token, refresh_token, expires_at, verified_at))
        self.conn.commit()

    def update_token(
        self,
        user_id: str,
        guild_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: float,
    ):
        self.conn.execute("""
            UPDATE verified_members
            SET access_token = ?, refresh_token = ?, expires_at = ?
            WHERE user_id = ? AND guild_id = ?
        """, (access_token, refresh_token, expires_at, user_id, guild_id))
        self.conn.commit()

    # ── Queries ──────────────────────────────────────────────
    def get_verified_members(self, guild_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM verified_members WHERE guild_id = ?", (guild_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_member(self, user_id: str, guild_id: str) -> Optional[dict]:
        cur = self.conn.execute(
            "SELECT * FROM verified_members WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def count_verified(self, guild_id: str) -> int:
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM verified_members WHERE guild_id = ?", (guild_id,)
        )
        return cur.fetchone()[0]

    def delete_member(self, user_id: str, guild_id: str):
        self.conn.execute(
            "DELETE FROM verified_members WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        self.conn.commit()
