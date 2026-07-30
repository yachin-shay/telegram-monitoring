# Telegram OSINT Collector

An authorized, account-scoped Telegram collector using Telethon and OpenTele2.
It accepts an existing authenticated Telegram Desktop `tdata` directory,
converts it into a separate Telethon session, then stores selected chat
histories and real-time updates in SQLite.

It never modifies the source `tdata`, extracts private TDLib keys, bypasses
Telegram privacy controls, or provides access beyond the authenticated account.

## Current capabilities

- One foreground Telethon daemon and session per account.
- Safe `tdata` → Telethon session conversion.
- Multi-terminal control through an owner-only Unix socket.
- Strict, versioned YAML configuration as the source of truth.
- Joined-chat metadata persistence and target selection by numeric chat ID.
- Selected-chat history jobs with page checkpoints and targeted real-time updates.
- Unlimited message revisions and non-destructive deletion markers.
- Explicit user scrape jobs with profile-photo pagination.
- Per-target media policy and content-addressed file-storage primitive.
- SQLite storage and plugin-outbox primitives.

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

Convert an existing authenticated Desktop profile first:

```bash
.venv/bin/tg-osint --config config.yaml session import-tdata \
  --tdata /secure/path/TelegramDesktop/tdata \
  --output state/research-1/account.session
```

The source directory is read-only. The command prompts for a Desktop passcode
without accepting it as a command-line argument.

Start the foreground daemon:

```bash
.venv/bin/tg-osint --config config.yaml daemon
```

Use other terminals for control:

```bash
.venv/bin/tg-osint --config config.yaml status
.venv/bin/tg-osint --config config.yaml chats
.venv/bin/tg-osint --config config.yaml targets add -1001234567890
.venv/bin/tg-osint --config config.yaml targets media \
  -1001234567890 --enabled true
.venv/bin/tg-osint --config config.yaml user-scrape 123456789 \
  --photos all_visible_history
```

## Documentation

- [Implementation plan](.sets-plan/first-plan/README.md)
- [Telegram profile-data research](docs/telegram-profile-data.md)

The first release targets Linux because it uses Unix sockets and `flock`.
Telegram visibility and member-list restrictions still apply; “all” always
means all data visible to the authenticated account at collection time.
