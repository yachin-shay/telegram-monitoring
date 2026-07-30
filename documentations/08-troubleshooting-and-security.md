# Troubleshooting and security

## “session is not authenticated”

The session file exists but Telethon returned no user. Run:

```bash
.venv/bin/tg-osint --config config.yaml session login-qr
```

Check that `paths.session` in the YAML is the same path used during login.
Also verify `TELEGRAM_API_HASH` and `account.api_id`.

## “another daemon owns this account instance”

A second daemon is using the same session lock. Stop the first process or use a
different configuration with separate paths. Never remove a lock file while a
process may still hold it; the lock is released automatically when the process
exits.

## Import conversion errors

Check that:

- the `--tdata` path is a real directory;
- Telegram Desktop is closed while importing;
- the local Telegram Desktop passcode is correct;
- the output path is not inside `tdata`;
- the destination is not being used by a daemon.

The importer refuses a source that changes while conversion runs.

## Jobs are failing

Use the control socket to inspect the job:

```bash
.venv/bin/tg-osint --config config.yaml job-show JOB_ID
```

Inspect `last_error`, `attempts`, and the daemon log. Network errors,
permissions, invalid chat IDs, revoked access, and Telegram rate limits are
common causes.

## Sensitive files

Treat these as credentials or sensitive intelligence:

- `paths.session` and its conversion manifest;
- Telegram Desktop `tdata`;
- the SQLite database;
- downloaded media;
- API hashes and environment files;
- daemon logs and exported JSON.

Recommended permissions:

```bash
chmod 700 state state/research-1
chmod 600 state/research-1/account.session \
  state/research-1/account.session.manifest.json
```

Use an encrypted disk or encrypted backup for state. Do not commit any
credential, `tdata`, database, media, or generated `config.yaml` file.

## Operational limitations

The collector can only observe data returned to the authorized Telegram
account. Deleted updates may not contain a peer for private chats; complete
deletion attribution depends on previously persisted message ownership.
Telegram API limits, connectivity, and account permissions can delay or
prevent collection. Historical profile photos are limited to what Telegram
makes visible to the authenticated account.
