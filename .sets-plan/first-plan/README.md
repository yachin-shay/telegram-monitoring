# Telegram OSINT Collector — First Implementation Plan

> Superseding implementation decision (2026-07-30): the runtime collector uses
> Telethon, not TDLib. An existing Telegram Desktop `tdata` directory is
> converted read-only into a separate Telethon session by pinned OpenTele2.
> TDLib-specific authentication and session-generation work is not part of the
> active runtime plan.

## Purpose

This plan describes a lawful, account-scoped Telegram collection tool built
around TDLib. It archives selected chat histories, persists real-time updates,
enriches explicitly requested users, optionally downloads media and visible
profile-photo history, and exposes modular pipelines and plugins.

The tool does not fabricate Telegram Desktop `tdata`, bypass privacy controls,
or access data unavailable to the authenticated account. TDLib's encrypted
database is the session store.

## Agreed product decisions

- Python 3.12+ owns orchestration; native `libtdjson` owns Telegram protocol,
  encryption, synchronization, and session persistence.
- One foreground daemon owns one Telegram account and one TDLib session.
- Many CLI terminals control the daemon through a local Unix socket.
- YAML is the persistent configuration source of truth.
- Startup flags are temporary overrides; explicit management commands rewrite
  YAML atomically.
- SQLite stores collected data, runtime state, cursors, and jobs. The daemon is
  its only writer; concurrent reporting processes are read-only.
- All joined chats can be listed. Only selected chats receive history backfill
  and real-time persistence.
- Media policy is configurable per target chat.
- Message revisions are unbounded. Deletion sets `is_deleted`; it does not erase
  captured content.
- User enrichment can be requested explicitly by user ID.
- Profile-photo history means all history visible to the authenticated account,
  never universal history.

## Plan map

| File | Scope |
| --- | --- |
| [00-scope-and-decisions.md](00-scope-and-decisions.md) | Boundaries, terminology, non-goals, unresolved choices |
| [01-architecture.md](01-architecture.md) | Processes, modules, data flow, concurrency |
| [02-foundation-and-packaging.md](02-foundation-and-packaging.md) | Repository, dependencies, `libtdjson`, CI |
| [03-configuration-and-cli.md](03-configuration-and-cli.md) | YAML model, CLI, atomic edits, daemon control |
| [04-tdlib-and-daemon.md](04-tdlib-and-daemon.md) | TDLib adapter, QR login, lifecycle, IPC |
| [05-storage-and-schema.md](05-storage-and-schema.md) | SQLite ownership, schema, migrations, revisions |
| [06-collection-pipelines.md](06-collection-pipelines.md) | Chat discovery, history, live updates, checkpoints |
| [07-profiles-and-media.md](07-profiles-and-media.md) | User enrichment, photos, membership, file storage |
| [08-plugins.md](08-plugins.md) | Plugin contracts, pipeline stages, isolation |
| [09-security-and-operations.md](09-security-and-operations.md) | Secrets, logging, recovery, retention, deployment |
| [10-testing-and-validation.md](10-testing-and-validation.md) | Test pyramid, fixtures, benchmarks, release gates |
| [11-delivery-roadmap.md](11-delivery-roadmap.md) | Ordered phases, task dependencies, milestones |

The official API research supporting profile collection is in
[`docs/telegram-profile-data.md`](../../docs/telegram-profile-data.md).

## Definition of the first production-capable release

The first release is complete when an operator can:

1. Start a foreground daemon with a valid YAML file.
2. authenticate an owned/authorized account through Telegram's supported flow;
3. list joined chats from another terminal;
4. add several target chat IDs and configure each media policy;
5. resume full-history backfills after interruption without duplicate records;
6. observe new messages, edits, deletions, and supported metadata updates in
   SQLite;
7. request enrichment of a visible user ID and optionally download all visible
   profile photos;
8. inspect and cancel durable jobs;
9. install a plugin without modifying collector internals;
10. stop the daemon cleanly without corrupting TDLib or SQLite state.
