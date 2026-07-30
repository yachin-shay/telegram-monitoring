# 00 — Scope and Decisions

## Superseding session decision

The collector accepts an existing authenticated Telegram Desktop `tdata`
directory and converts it to a separate Telethon session using OpenTele2. The
source remains read-only. Telethon owns the runtime session; TDLib is not a
runtime dependency. OpenTele2 cannot consume a TDLib database, so no TDLib
session conversion is attempted.

## Authorization boundary

The operator must supply their own Telegram `api_id` and `api_hash` and
authenticate an account they own or are authorized to operate. Every query is
limited to what Telegram returns to that account. The application must preserve
the distinction between:

- `known`: Telegram returned a value;
- `empty`: Telegram explicitly returned no value;
- `unknown`: the value was unavailable, not requested, or privacy-restricted.

The UI and exports must use phrases such as "visible members" and "all visible
profile photos," not claim completeness Telegram cannot guarantee.

## In scope

- QR-code and supported phone-code authentication through TDLib.
- TDLib encrypted session databases, one account per daemon.
- Joined-chat discovery and target selection by stable numeric chat ID.
- Resumable selected-chat history collection.
- Real-time message/update persistence for selected chats.
- Unlimited message revisions and non-destructive deletion markers.
- Latest-state and change-observation tables for users, chats, memberships, and
  profile metadata.
- Explicit user-ID enrichment jobs.
- Configurable member scans where Telegram exposes the member list.
- Per-chat media and profile-photo download policies.
- Filesystem media storage with SQLite metadata and hashes.
- YAML configuration modified through explicit CLI commands.
- Local multi-terminal operation through daemon IPC.
- Pipeline and plugin extension points.
- Structured operational/audit logs.

## Deferred or excluded

- Telegram Desktop-compatible `tdata` generation or conversion.
- Secret-chat history collection; TDLib and Telegram constraints must be
  documented separately before any promise is made.
- Bypassing privacy, deleted-content recovery, account compromise, session
  stealing, or bulk unsolicited account discovery.
- Distributed multi-host collection and a central database.
- A web dashboard.
- PostgreSQL and object-storage backends.
- Automatic OCR, face recognition, sentiment analysis, or AI training.
- Raw MTProto as the default transport. It may become an adapter only when a
  documented, tested TDLib gap requires it.

## Domain terminology

- **Account instance:** YAML, TDLib directory, SQLite database, and media root
  belonging to one authorized account.
- **Daemon:** foreground process exclusively owning that account instance.
- **Target:** a chat selected for history and/or live collection.
- **Observation:** data known at a specific time, without claiming it changed at
  that exact time.
- **Revision:** one captured version of a Telegram message.
- **Job:** durable unit such as history backfill, user scrape, member scan, or
  download.
- **Raw object:** versioned JSON returned by TDLib before normalization.
- **Visible:** returned or accessible to the authenticated account.

## Decisions to confirm during implementation

These do not block the architecture, but each phase must record its answer in an
ADR before code depending on it is merged:

1. Supported platforms for release one: recommend Linux x86-64 first.
2. Packaging: recommend a Python wheel plus a separately verified `libtdjson`
   system/package artifact; add a container image after the native build is
   reproducible.
3. YAML library: select one that can round-trip comments if CLI edits must
   preserve hand-written formatting.
4. IPC serialization: recommend newline-delimited JSON over a permission-scoped
   Unix socket for version one.
5. SQLite encryption at rest: recommend documenting filesystem/disk encryption
   first; evaluate SQLCipher as an optional backend rather than implying stock
   SQLite encryption.
6. Plugin trust: version one supports trusted in-process plugins only; untrusted
   plugins require subprocess isolation in a later release.
