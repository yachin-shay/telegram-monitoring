# 05 — Storage and Schema

## DB-01: Database ownership and migrations

**Depends on:** FND-03.

Open SQLite in WAL mode, enable foreign keys, configure a measured busy timeout,
and make the daemon's connection the sole writer. Record application schema,
TDLib version, account-instance ID, and migration history.

Migrations are forward-only in production. Each migration runs transactionally
where SQLite permits, has a fixture upgrade test, and documents backup/recovery.
Refuse to open a schema newer than the application.

At startup, verify that the configured SQLite path is not shared by another
account instance. Maintain an owner marker containing account ID after login,
without exposing credentials.

## DB-02: Core identity and raw-object schema

**Depends on:** DB-01.

Create:

- `accounts`, `chats`, `chat_user_links`, `supergroups`, `basic_groups`;
- `users`, `user_full_info`, `user_usernames`;
- `raw_objects` keyed by source type, Telegram identity, observation time,
  TDLib version, and content hash;
- `collection_runs` and `collection_errors`.

Use Telegram IDs as signed 64-bit integers. Store timestamps consistently as UTC
Unix seconds/milliseconds plus an observed-at timestamp. Never overload `NULL`:
add state columns when unknown and empty are semantically different.

Store latest normalized rows separately from append-only observations. Upsert
latest state and insert a snapshot only when canonical content changes.

## DB-03: Message and revision schema

**Depends on:** DB-02.

Create:

- `messages`: chat ID, message ID, sender identity, thread/topic, reply/forward
  relationships, dates, latest revision ID, `is_deleted`, deletion observation;
- `message_revisions`: unlimited sequence per message, edit date, captured date,
  text/caption, entities, content type, normalized content JSON, raw-object ID;
- child tables for entities, reactions, interaction info, polls, locations,
  contacts, service actions, and file references where querying warrants it;
- `message_events`: append-only receipt of create/edit/delete/pin/reaction and
  other update categories.

Uniqueness is `(account_id, chat_id, message_id)` and
`(message_pk, revision_sequence)`. Duplicate delivery must be idempotent. A
revision is inserted only when normalized content or relevant metadata changes;
each observed update still may create an event record.

Deletion updates set `is_deleted = true`; never delete revisions or media
metadata automatically. If an undeleted message is later observed, record the
new evidence rather than silently toggling without an event.

## DB-04: Profiles, membership, and files

**Depends on:** DB-02.

Create:

- `user_profile_observations`, `user_status_observations`;
- `user_photos`, `user_photo_files`;
- `chat_member_observations`, `member_scan_runs`;
- `files`, `file_sources`, `download_attempts`;
- `target_runtime_state`.

Membership scans record filter, pagination cursor, expected and returned counts,
capability flags, start/end times, completeness classification, and terminal
error. Absence is never interpreted as departure without comparable complete
evidence or an explicit update.

Files store Telegram identifiers, remote/local state, expected and actual size,
MIME type, content hash, relative path, and verification status. Binary content
does not enter SQLite.

## DB-05: Durable job scheduler schema

**Depends on:** DB-01.

Create `jobs`, `job_attempts`, `job_dependencies`, and `job_checkpoints`.
Lifecycle states are queued, running, waiting, succeeded, failed, cancelled, and
blocked. Store typed payloads with a schema version, priority, deduplication key,
lease/heartbeat, retry time, progress, and last error.

On restart, expired running leases return to queued or waiting. Cancellation is
cooperative and checkpoints before exit. Deduplicate user scrapes and backfills
without preventing a deliberate forced refresh.

## DB-06: Query and export boundary

**Depends on:** DB-03, DB-04.

Provide read-only repository queries and documented SQL views for common
analysis. Export jobs must snapshot a consistent read transaction and redact
configured sensitive fields. Do not expose mutable ORM objects to plugins.

Add database metadata and integrity commands. Document safe backup using the
SQLite backup API rather than copying active database/WAL files independently.

