# Architecture

## Runtime shape

Each account is an independent foreground process:

```text
config.yaml
    │
    ├── Telethon session ── TelethonAdapter ── Telegram API
    │                              │
    ├── SQLite database ─────── Collector ─── message/profile events
    │                              │
    ├── media directory ─────── MediaStore
    └── Unix socket ─────────── ControlServer
```

The process owns one Telethon session, one SQLite writer, one media root, and
one Unix-domain control socket. Running multiple accounts means running
multiple daemon commands with separate configuration paths.

## Authentication boundary

There are two supported ways to create the Telethon session:

- `session login-qr` performs a fresh Telethon QR login and creates an
  independent authorization.
- `session import-tdata` reads an existing Telegram Desktop `tdata` directory
  through OpenTele2 and writes a Telethon session.

The importer writes to a temporary sibling directory, validates the generated
session with `get_me()`, fingerprints the source before and after conversion,
and atomically replaces the destination when `--force` is used. The source is
never intentionally modified. A manifest is written beside the session.

The daemon does not perform interactive login. It requires
`paths.session` to exist and to be authorized before collection starts.

## Startup sequence

1. Parse and validate YAML.
2. Acquire the account session lock.
3. Create the media directory and verify the session file.
4. Migrate the SQLite schema.
5. Connect Telethon.
6. Register update handlers immediately after connecting.
7. Call `get_me()` and set the account ID.
8. Discover and persist joined dialogs.
9. Start the Unix control socket.
10. Enqueue configured history jobs.
11. Run the job worker and wait for SIGINT/SIGTERM.

Early event subscription is deliberate: dialog discovery and identity calls
are network operations during which realtime updates may arrive.

## Shutdown

On SIGINT or SIGTERM, the daemon cancels the job loop, closes the control
socket, disconnects Telethon, closes SQLite, and releases the lock. The daemon
is foreground-native; use a supervisor such as systemd, tmux, or a container
runtime if it must be restarted automatically.

## Module responsibilities

- `cli.py`: command parsing and user-facing commands.
- `config.py`: strict YAML parsing and atomic target mutations.
- `session.py`: QR login and OpenTele2 conversion.
- `telethon_adapter.py`: Telethon-to-collector boundary.
- `collector.py`: message update normalization and revision/deletion handling.
- `jobs.py`: durable history and user-scrape workers.
- `storage.py`: SQLite schema, transactions, and outbox.
- `media.py`: content-addressed media finalization.
- `ipc.py`: authenticated local control protocol.
- `plugins.py`: at-least-once outbox dispatch abstraction.
