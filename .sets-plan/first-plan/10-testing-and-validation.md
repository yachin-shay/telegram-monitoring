# 10 — Testing and Validation

## Test layers

### Unit tests

Cover configuration, canonical hashes, domain normalization, policy resolution,
message revision decisions, ID/timestamp handling, retry classification, path
sanitization, and plugin contracts. Use property-based tests for pagination,
deduplication, and state-machine transitions where valuable.

### Contract tests

Capture sanitized TDLib JSON fixtures for every authorization state, chat type,
message content type, edit/delete form, user/full-info state, membership result,
file update, and representative error. Run the adapter and normalizers against
fixtures from the pinned TDLib version.

Fixture sanitization must replace identifiers and content deterministically and
be reviewed so no real user data enters the repository.

### Database tests

- Migrate an empty database and every historical fixture.
- Enforce foreign keys and uniqueness.
- Replay identical and reordered events.
- Verify unlimited revisions and deletion markers.
- Crash between page persistence and checkpoint update.
- Run concurrent read-only clients during sustained writes.
- Exercise backup/restore and integrity checks.

### Integration tests

Use a fake TDLib transport for deterministic daemon, IPC, scheduler, and pipeline
tests. Run native adapter smoke tests separately. Maintain a manual authorized
Telegram test-account runbook for QR login and real network behavior; never run
network tests automatically with developer credentials.

### Plugin tests

Test at-least-once delivery, replay, backpressure, timeout, crashes,
incompatibility, invalid configuration, and dead-letter recovery. Confirm plugin
failure cannot prevent core commits.

## VAL-01: Correctness release gate

The release candidate must demonstrate:

- message IDs and int64 values round-trip exactly;
- updates remain ordered through receive and persistence;
- history/live overlap produces one message with correct revisions;
- restarts resume every durable job without silent gaps;
- all errors are either retried under policy or recorded terminally;
- unsupported TDLib fields remain recoverable from raw JSON;
- deletion never erases captured revisions.

## VAL-02: Performance and soak gate

Build a deterministic load generator around the fake TDLib transport. Measure:

- updates per second at receive, normalize, and commit stages;
- p50/p95/p99 receive-to-commit latency;
- queue depth and memory growth;
- WAL growth/checkpoint behavior;
- plugin lag;
- media hashing/download worker impact.

Run a 24-hour soak with live-like update mixtures and injected plugin/database
delays. Establish capacity from measurements rather than a promised number.
The daemon must keep memory bounded and expose growing backlog before failure.

## VAL-03: Security and recovery gate

Verify socket permissions and peer checks, secret redaction, unsafe path
rejection, config conflict protection, malicious filenames, oversized IPC
frames, malformed plugin events, and least-privilege deployment examples.

Simulate `SIGTERM`, `SIGKILL`, disk full, corrupt YAML, unavailable `libtdjson`,
revoked authorization, flood wait, SQLite busy/corruption, and media-root loss.
Document the expected operator response for each.

## Release evidence

Every release stores:

- application and TDLib versions/checksums;
- migration compatibility result;
- automated test report;
- benchmark/soak summary;
- known Telegram API limitations;
- configuration schema and plugin API versions;
- manual test-account checklist result.

