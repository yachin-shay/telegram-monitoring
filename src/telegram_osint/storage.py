from __future__ import annotations

import json
import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from telegram_osint.domain import Job, MessageEvent, MessageRevision


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    latest_revision INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    deleted_observed_at INTEGER,
    PRIMARY KEY (account_id, chat_id, message_id)
);
CREATE TABLE IF NOT EXISTS message_revisions (
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    revision_sequence INTEGER NOT NULL,
    observed_at INTEGER NOT NULL,
    text TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (account_id, chat_id, message_id, revision_sequence),
    FOREIGN KEY (account_id, chat_id, message_id)
      REFERENCES messages (account_id, chat_id, message_id)
);
CREATE TABLE IF NOT EXISTS message_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    revision_sequence INTEGER,
    UNIQUE (
      account_id, chat_id, message_id, event_type, observed_at, revision_sequence
    )
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    state TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    deduplication_key TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_active_dedup
ON jobs(deduplication_key)
WHERE deduplication_key IS NOT NULL
  AND state IN ('queued', 'running', 'waiting');
CREATE TABLE IF NOT EXISTS chats (
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    chat_type TEXT NOT NULL,
    username TEXT,
    raw_json TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    PRIMARY KEY (account_id, chat_id)
);
CREATE TABLE IF NOT EXISTS users (
    account_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    phone_number TEXT,
    raw_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    PRIMARY KEY (account_id, user_id)
);
CREATE TABLE IF NOT EXISTS user_profile_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    UNIQUE(account_id, user_id, content_hash)
);
CREATE TABLE IF NOT EXISTS user_full_info (
    account_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    PRIMARY KEY (account_id, user_id)
);
CREATE TABLE IF NOT EXISTS user_photos (
    account_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    photo_id INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    PRIMARY KEY (account_id, user_id, photo_id)
);
CREATE TABLE IF NOT EXISTS plugin_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS plugin_deliveries (
    plugin_name TEXT NOT NULL,
    outbox_id INTEGER NOT NULL,
    delivered_at INTEGER NOT NULL,
    PRIMARY KEY (plugin_name, outbox_id),
    FOREIGN KEY (outbox_id) REFERENCES plugin_outbox(id)
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")

    def close(self) -> None:
        self.connection.close()

    def migrate(self) -> None:
        with self.connection:
            self.connection.executescript(SCHEMA)
            self.connection.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(1, ?)",
                (int(time.time()),),
            )

    def persist_message(
        self,
        revision: MessageRevision,
        event: MessageEvent,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO messages(account_id, chat_id, message_id, latest_revision)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(account_id, chat_id, message_id) DO UPDATE SET
                  latest_revision = MAX(latest_revision, excluded.latest_revision)
                """,
                (
                    revision.account_id,
                    revision.chat_id,
                    revision.message_id,
                    revision.revision_sequence,
                ),
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO message_revisions(
                  account_id, chat_id, message_id, revision_sequence,
                  observed_at, text, raw_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision.account_id,
                    revision.chat_id,
                    revision.message_id,
                    revision.revision_sequence,
                    revision.observed_at,
                    revision.text,
                    json.dumps(revision.raw, sort_keys=True),
                ),
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO message_events(
                  account_id, chat_id, message_id, event_type,
                  observed_at, revision_sequence
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    revision.account_id,
                    revision.chat_id,
                    revision.message_id,
                    event.value,
                    revision.observed_at,
                    revision.revision_sequence,
                ),
            )
            self._outbox(
                event.value,
                {
                    "account_id": revision.account_id,
                    "chat_id": revision.chat_id,
                    "message_id": revision.message_id,
                    "revision": revision.revision_sequence,
                },
            )

    def mark_deleted(
        self,
        *,
        account_id: int,
        chat_id: int,
        message_id: int,
        observed_at: int,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO messages(
                  account_id, chat_id, message_id, is_deleted, deleted_observed_at
                ) VALUES(?, ?, ?, 1, ?)
                ON CONFLICT(account_id, chat_id, message_id) DO UPDATE SET
                  is_deleted = 1, deleted_observed_at = excluded.deleted_observed_at
                """,
                (account_id, chat_id, message_id, observed_at),
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO message_events(
                  account_id, chat_id, message_id, event_type, observed_at
                ) VALUES(?, ?, ?, 'deleted', ?)
                """,
                (account_id, chat_id, message_id, observed_at),
            )
            self._outbox(
                "deleted",
                {
                    "account_id": account_id,
                    "chat_id": chat_id,
                    "message_id": message_id,
                },
            )

    def get_message(
        self,
        account_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT * FROM messages
            WHERE account_id = ? AND chat_id = ? AND message_id = ?
            """,
            (account_id, chat_id, message_id),
        ).fetchone()
        if row is None:
            return None
        revisions = self.connection.execute(
            """
            SELECT * FROM message_revisions
            WHERE account_id = ? AND chat_id = ? AND message_id = ?
            ORDER BY revision_sequence
            """,
            (account_id, chat_id, message_id),
        ).fetchall()
        result = dict(row)
        result["revisions"] = [dict(item) for item in revisions]
        return result

    def enqueue_job(
        self,
        *,
        kind: str,
        payload: dict[str, Any],
        deduplication_key: str | None = None,
    ) -> str:
        job_id = f"job_{uuid.uuid4().hex}"
        now = int(time.time())
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO jobs(
                      id, kind, state, payload_json, deduplication_key,
                      created_at, updated_at
                    ) VALUES(?, ?, 'queued', ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        kind,
                        json.dumps(payload, sort_keys=True),
                        deduplication_key,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError:
            row = self.connection.execute(
                """
                SELECT id FROM jobs
                WHERE deduplication_key = ?
                  AND state IN ('queued', 'running', 'waiting')
                """,
                (deduplication_key,),
            ).fetchone()
            if row is None:
                raise
            return str(row["id"])
        return job_id

    def claim_next_job(self) -> Job | None:
        with self.connection:
            row = self.connection.execute(
                "SELECT * FROM jobs WHERE state = 'queued' ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            self.connection.execute(
                """
                UPDATE jobs SET state = 'running', attempts = attempts + 1,
                  updated_at = ? WHERE id = ? AND state = 'queued'
                """,
                (int(time.time()), row["id"]),
            )
        return self.get_job(str(row["id"]))

    def complete_job(self, job_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE jobs SET state = 'succeeded', updated_at = ? WHERE id = ?",
                (int(time.time()), job_id),
            )

    def fail_job(self, job_id: str, error: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE jobs SET state = 'failed', last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (error, int(time.time()), job_id),
            )

    def get_job(self, job_id: str) -> Job:
        row = self.connection.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return Job(
            id=str(row["id"]),
            kind=str(row["kind"]),
            state=str(row["state"]),
            payload=json.loads(row["payload_json"]),
            attempts=int(row["attempts"]),
        )

    def list_chats(self, account_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM chats WHERE account_id = ? ORDER BY title, chat_id",
            (account_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def upsert_chat(
        self,
        *,
        account_id: int,
        chat_id: int,
        title: str,
        chat_type: str,
        username: str | None,
        raw: dict[str, Any],
        observed_at: int,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO chats(
                  account_id, chat_id, title, chat_type, username,
                  raw_json, observed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, chat_id) DO UPDATE SET
                  title = excluded.title,
                  chat_type = excluded.chat_type,
                  username = excluded.username,
                  raw_json = excluded.raw_json,
                  observed_at = excluded.observed_at
                """,
                (
                    account_id,
                    chat_id,
                    title,
                    chat_type,
                    username,
                    json.dumps(raw, sort_keys=True),
                    observed_at,
                ),
            )

    def upsert_user(
        self,
        *,
        account_id: int,
        user_id: int,
        first_name: str | None,
        last_name: str | None,
        username: str | None,
        phone_number: str | None,
        raw: dict[str, Any],
        observed_at: int,
    ) -> None:
        raw_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(raw_json.encode()).hexdigest()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO users(
                  account_id, user_id, first_name, last_name, username,
                  phone_number, raw_json, content_hash, observed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, user_id) DO UPDATE SET
                  first_name = excluded.first_name,
                  last_name = excluded.last_name,
                  username = excluded.username,
                  phone_number = excluded.phone_number,
                  raw_json = excluded.raw_json,
                  content_hash = excluded.content_hash,
                  observed_at = excluded.observed_at
                """,
                (
                    account_id,
                    user_id,
                    first_name,
                    last_name,
                    username,
                    phone_number,
                    raw_json,
                    content_hash,
                    observed_at,
                ),
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO user_profile_observations(
                  account_id, user_id, content_hash, observed_at, raw_json
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (account_id, user_id, content_hash, observed_at, raw_json),
            )

    def next_revision_sequence(
        self,
        *,
        account_id: int,
        chat_id: int,
        message_id: int,
    ) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(revision_sequence), 0) + 1
            FROM message_revisions
            WHERE account_id = ? AND chat_id = ? AND message_id = ?
            """,
            (account_id, chat_id, message_id),
        ).fetchone()
        return int(row[0])

    def _outbox(self, event_type: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO plugin_outbox(event_type, payload_json, created_at)
            VALUES(?, ?, ?)
            """,
            (event_type, json.dumps(payload, sort_keys=True), int(time.time())),
        )

    def enqueue_outbox(self, event_type: str, payload: dict[str, Any]) -> None:
        with self.connection:
            self._outbox(event_type, payload)

    def persist_user_full_info(
        self,
        *,
        account_id: int,
        user_id: int,
        raw: dict[str, Any],
        observed_at: int,
    ) -> None:
        raw_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(raw_json.encode()).hexdigest()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO user_full_info(
                  account_id, user_id, raw_json, content_hash, observed_at
                ) VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(account_id, user_id) DO UPDATE SET
                  raw_json = excluded.raw_json,
                  content_hash = excluded.content_hash,
                  observed_at = excluded.observed_at
                """,
                (account_id, user_id, raw_json, content_hash, observed_at),
            )

    def persist_user_photo(
        self,
        *,
        account_id: int,
        user_id: int,
        photo_id: int,
        raw: dict[str, Any],
        observed_at: int,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO user_photos(
                  account_id, user_id, photo_id, raw_json, observed_at
                ) VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(account_id, user_id, photo_id) DO UPDATE SET
                  raw_json = excluded.raw_json,
                  observed_at = excluded.observed_at
                """,
                (
                    account_id,
                    user_id,
                    photo_id,
                    json.dumps(raw, sort_keys=True),
                    observed_at,
                ),
            )

    def pending_outbox(self, plugin_name: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT o.* FROM plugin_outbox AS o
            LEFT JOIN plugin_deliveries AS d
              ON d.outbox_id = o.id AND d.plugin_name = ?
            WHERE d.outbox_id IS NULL
            ORDER BY o.id
            """,
            (plugin_name,),
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "type": str(row["event_type"]),
                "payload": json.loads(row["payload_json"]),
                "created_at": int(row["created_at"]),
            }
            for row in rows
        ]

    def mark_outbox_delivered(self, plugin_name: str, outbox_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO plugin_deliveries(
                  plugin_name, outbox_id, delivered_at
                ) VALUES(?, ?, ?)
                """,
                (plugin_name, outbox_id, int(time.time())),
            )
