# Telegram OSINT Collector

An authorized, account-scoped Telegram collector using Python and TDLib. It
stores selected chat histories and real-time updates in SQLite, preserves every
observed message revision, marks deletions without erasing evidence, enriches
visible user profiles, and optionally collects all profile photos visible to the
authenticated account.

It does not generate Telegram Desktop `tdata`, bypass Telegram privacy controls,
or provide access beyond the authenticated account.

## Current capabilities

- One foreground daemon and TDLib session per account.
- QR authentication with phone/code/2FA fallback controls.
- Multi-terminal control through an owner-only Unix socket.
- Strict, versioned YAML configuration as the source of truth.
- Joined-chat metadata persistence and target selection by numeric chat ID.
- Selected-chat history jobs with page checkpoints and targeted real-time updates.
- Unlimited message revisions and non-destructive deletion markers.
- Explicit user scrape jobs with full-info and visible photo-history pagination.
- Per-target media policy and a content-addressed file-storage primitive.
- SQLite WAL storage and plugin-outbox primitives.

## Development setup

Create the required project-local environment with `uv`:

```bash
uv venv --system-site-packages .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/python -m pytest
```

Do not install project dependencies into the system Python environment.

## Configuration

Copy [`config.example.yaml`](config.example.yaml), provide your own Telegram API
credentials, and keep the API hash outside YAML:

```bash
cp config.example.yaml config.yaml
export TELEGRAM_API_HASH='your-api-hash'
```

Build TDLib's `tdjson` target from an explicitly pinned official release, then
start the foreground daemon:

```bash
.venv/bin/tg-osint --config config.yaml daemon \
  --tdjson /absolute/path/to/libtdjson.so
```

Use other terminals for control:

```bash
.venv/bin/tg-osint --config config.yaml auth status
.venv/bin/tg-osint --config config.yaml auth qr
.venv/bin/tg-osint --config config.yaml chats
.venv/bin/tg-osint --config config.yaml targets add -1001234567890
.venv/bin/tg-osint --config config.yaml targets media \
  -1001234567890 --enabled true
.venv/bin/tg-osint --config config.yaml user-scrape 123456789 \
  --photos all_visible_history
```

Authentication codes and 2FA passwords are prompted securely and are not
accepted as command arguments.

## Documentation

- [Implementation plan](.sets-plan/first-plan/README.md)
- [Telegram profile-data research](docs/telegram-profile-data.md)

The first release targets Linux because it uses Unix sockets and `flock`.
Telegram visibility and member-list restrictions still apply; “all” always
means all data visible to the authenticated account at collection time.
