# Running and operations

## Start the foreground daemon

```bash
.venv/bin/tg-osint --config config.yaml daemon
```

The process logs to its configured logging destination and remains attached to
the terminal. This makes exit status, signals, and supervisor integration
predictable.

## Control commands

Run these from another terminal while the daemon owns the socket:

```bash
.venv/bin/tg-osint --config config.yaml status
.venv/bin/tg-osint --config config.yaml chats
.venv/bin/tg-osint --config config.yaml targets list
.venv/bin/tg-osint --config config.yaml user-scrape 123456789
.venv/bin/tg-osint --config config.yaml job-show JOB_ID
.venv/bin/tg-osint --config config.yaml job-show JOB_ID --watch
```

Pass `--json` before the subcommand when machine-readable output is needed:

```bash
.venv/bin/tg-osint --config config.yaml --json chats
```

`job-show --watch` polls the durable job record and prints each state or
progress change until the job succeeds or fails. The daemon also logs job
start, completion, and failure events in its foreground output.

## Multiple accounts

Use one YAML file and one daemon process per account:

```bash
.venv/bin/tg-osint --config accounts/alice.yaml daemon
.venv/bin/tg-osint --config accounts/bob.yaml daemon
```

Do not share session, database, media, or socket paths between accounts.

## Recovery and restart

The SQLite migration requeues jobs that were marked `running` when the process
stopped. History jobs checkpoint their pagination cursor, so a restart resumes
from the most recent checkpoint rather than relying on in-memory state.

If a session is revoked, stop the daemon, run `session login-qr`, and restart.
Do not delete the database unless loss of collected data is acceptable.

## Supervisors

For systemd, configure the process as a foreground service and use
`Restart=on-failure`. Keep the YAML, session, database, media, and socket in a
directory readable only by the service account. Container deployments should
mount the state directory persistently.
