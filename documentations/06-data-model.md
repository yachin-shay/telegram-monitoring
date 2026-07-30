# SQLite data model

The configured database is SQLite in WAL mode with foreign keys and a
five-second busy timeout. The schema is created by `Database.migrate()`.

## Accounts and chats

`accounts` identifies the authenticated account observed by the daemon.
`chats` stores discovered dialogs with `chat_id`, title, type, username, raw
metadata, and observation time.

## Messages

`messages` is the stable identity row:

```text
(account_id, chat_id, message_id) → latest_revision, deletion state
```

`message_revisions` stores every observed text/raw snapshot with a
`revision_sequence`. `message_events` records semantic events such as new,
edited, and deleted.

Use `is_deleted` rather than deleting rows. This preserves auditability and
allows a consumer to distinguish “never collected” from “collected then
deleted”.

## Users

- `users`: latest basic user metadata and content hash.
- `user_profile_observations`: historical profile snapshots, deduplicated by
  content hash.
- `user_full_info`: latest full-user API response and hash.
- `user_photos`: visible profile-photo metadata keyed by photo ID.

Raw API responses are serialized as JSON. Telethon bytes are represented by the
adapter as base64-bearing objects, and timestamps are ISO strings where raw
metadata requires them.

## Jobs

`jobs` contains the durable queue:

- `kind`: `chat_history` or `user_scrape`.
- `state`: queued, running, waiting, or completed/failed state as managed by
  the storage layer.
- `payload_json`: cursor and request parameters.
- `deduplication_key`: prevents duplicate active jobs.
- `attempts`, timestamps, and `last_error`.

## Plugin outbox

`plugin_outbox` is an append-only event queue. `plugin_deliveries` records a
per-plugin delivery cursor, enabling at-least-once delivery semantics.

## Query examples

```sql
-- Deleted messages while retaining their revisions
SELECT chat_id, message_id, deleted_observed_at
FROM messages
WHERE account_id = ? AND is_deleted = 1;

-- All revisions of one message
SELECT revision_sequence, observed_at, text, raw_json
FROM message_revisions
WHERE account_id = ? AND chat_id = ? AND message_id = ?
ORDER BY revision_sequence;

-- Recent joined dialogs
SELECT chat_id, title, chat_type, username, observed_at
FROM chats
WHERE account_id = ?
ORDER BY title;
```
