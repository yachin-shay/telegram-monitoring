# Configuration

## Complete example

```yaml
schema_version: 1
account:
  name: research-1
  api_id: 123456
  api_hash_env: TELEGRAM_API_HASH
paths:
  tdata: state/research-1/tdata
  session: state/research-1/account.session
  database: state/research-1/collector.sqlite3
  media: state/research-1/media
  socket: state/research-1/daemon.sock
targets:
  "-1001234567890":
    history:
      enabled: true
    realtime:
      enabled: true
    media:
      enabled: true
      types: [photo, video, document]
      max_bytes: 104857600
    profiles:
      enabled: true
      snapshot_on_change: true
      photos:
        mode: all_visible_history
        download: false
        max_bytes: 20971520
plugins: {}
```

## Account

`account.name` identifies the process in the database and control responses.
`account.api_id` is an integer. `account.api_hash` may be used directly, but
`account.api_hash_env` is preferred and must name a non-empty environment
variable.

## Paths

All relative paths are resolved relative to the YAML file:

- `tdata`: optional source location used by operators for imports.
- `session`: Telethon SQLite session used by the daemon.
- `database`: collector SQLite database.
- `media`: finalized downloaded files.
- `socket`: Unix control socket.

Paths must be distinct. Each account needs distinct session, database, media,
and socket paths.

## Targets

Targets are keyed by Telegram chat ID. The daemon discovers all joined dialogs
and stores them in `chats`; only configured targets receive history jobs and
realtime collection.

Each target supports:

- `history.enabled`: enqueue historical backfill at startup.
- `realtime.enabled`: enable realtime policy for the target.
- `media.enabled`: allow media handling for this target.
- `media.types`: selected media classes.
- `media.max_bytes`: per-file size limit.
- `profiles.enabled`: enable profile observations.
- `profiles.snapshot_on_change`: retain changed profile snapshots.
- `profiles.photos.mode`: `off`, `current`, or `all_visible_history`.
- `profiles.photos.download`: whether profile photos are downloaded.
- `profiles.photos.max_bytes`: profile-photo size limit.

Media and photo settings are per target. There is no global media switch that
overrides a target’s explicit policy.

## Runtime configuration mutation

The `targets` commands atomically rewrite YAML and use an expected
configuration hash to prevent lost updates:

```bash
.venv/bin/tg-osint --config config.yaml targets add -1001234567890
.venv/bin/tg-osint --config config.yaml targets media \
  -1001234567890 --enabled true
.venv/bin/tg-osint --config config.yaml targets remove -1001234567890
```

If another process changed the YAML since the command loaded it, the mutation
is rejected and must be retried after reloading the configuration.
