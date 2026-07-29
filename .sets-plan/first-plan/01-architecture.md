# 01 — Architecture

## Runtime topology

```text
CLI clients ── Unix socket ──> foreground daemon
                                 │
                      ┌──────────┼───────────┐
                      │          │           │
                 TDLib adapter  scheduler  config manager
                      │          │           │
                   Telegram   pipelines     YAML
                                 │
                         single DB writer
                          │             │
                       SQLite       media files
```

Only the daemon opens TDLib and only its database writer mutates SQLite. CLI
clients never import the collector runtime or touch the TDLib directory.

## Proposed Python packages

```text
src/telegram_osint/
  cli/             command parsing, presentation, IPC client
  config/          schema, loading, validation, atomic mutation
  daemon/          lifecycle, signal handling, health, IPC server
  tdlib/           native loading, JSON transport, auth, typed envelopes
  domain/          stable internal events and value objects
  scheduler/       durable jobs, rate control, retries, cancellation
  collection/      chat discovery, history, live updates, profiles, members
  pipelines/       normalization, routing, persistence, plugin dispatch
  storage/         repositories, migrations, SQLite writer, queries
  media/           policy, downloads, hashing, content-addressed paths
  plugins/         contracts, discovery, loading, failure boundaries
  observability/   logs, metrics, audit events, redaction
```

Imports must point inward toward `domain` contracts. TDLib JSON types must not
leak into storage, CLI, or plugin APIs. This makes a future transport adapter
possible without pretending it is already needed.

## Ordered update path

1. A dedicated native receiver thread is the sole caller of `td_receive`.
2. It parses only enough JSON to attach client ID, type, and correlation ID.
3. It submits envelopes to a bounded bridge queue in exact receive order.
4. The asyncio dispatcher resolves request responses or routes updates.
5. Normalizers convert TDLib payloads into stable domain events.
6. Target policy decides whether an event is ignored, metadata-only, or fully
   collected.
7. A single transactional writer persists normalized rows, raw JSON, cursor
   changes, and outbox events.
8. Post-commit plugin consumers receive outbox events. Plugin failure cannot
   roll back core collection.

## Backpressure and concurrency

- Never run multiple concurrent receive calls.
- Use separate bounded concurrency pools for Telegram requests, file downloads,
  hashing, and plugins.
- The database writer accepts batches but commits often enough to bound data
  loss and WAL growth.
- Job priority order: live updates, auth/control, requested user scrape, history
  backfill, profile-photo/media downloads, periodic refresh.
- When queues are full, pause lower-priority producers; do not discard live
  update envelopes silently.
- Flood-wait responses suspend the affected account scheduler for the exact
  server-directed interval.

## Failure boundaries

- A malformed plugin is disabled and audited; the daemon remains alive.
- A corrupt event is moved to a dead-letter table with raw input and error.
- SQLite write failures stop collection rather than acknowledging unpersisted
  progress.
- TDLib authorization loss moves the daemon to `reauth_required`.
- Config validation failure retains the last valid in-memory configuration and
  reports the rejected file version.
- Disk-full state pauses downloads first, then collection if database writes
  cannot continue.

