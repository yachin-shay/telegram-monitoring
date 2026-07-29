# 09 — Security and Operations

## SEC-01: Secrets and local permissions

**Depends on:** CFG-01, DMN-01.

Reference `api_id`, `api_hash`, database encryption key, and 2FA inputs from
environment variables, protected files, or a future secret provider. Never put
secret values in YAML examples, command arguments, logs, SQLite raw payloads, or
crash reports.

Create state directories with owner-only permissions. Validate existing TDLib,
database, socket, and media paths before use. Refuse world-writable session
directories and unsafe symlink resolution.

## SEC-02: Audit and redaction

**Depends on:** CLI-01, DB-01.

Record authentication transitions, configuration mutations, target changes,
user scrape requests, job cancellation/retry, plugin state changes, exports,
and retention operations. Include request ID, actor evidence available locally,
time, result, and config hashes.

Use allowlisted structured log fields and recursive redaction for phone numbers,
auth codes, passwords, hashes, socket payloads, and sensitive Telegram content.
Core application logs should identify message/chat IDs only at debug level under
an explicit sensitive-logging setting.

## OPS-01: Observability

**Depends on:** DMN-01.

Structured logs go to stderr for supervisor capture. Status exposes daemon state,
account identity after authorization, TDLib version, config hash, database
schema, active targets, queue depths, last committed update, WAL size, disk
space, flood-wait state, and job counts.

Health has separate liveness and readiness semantics. Authentication-required,
database-read-only, disk-full, and backlog-over-limit states are not reported as
healthy readiness.

## OPS-02: systemd and container deployment

**Depends on:** DMN-01, FND-02, SEC-01.

Provide a hardened systemd example using foreground execution, restart policy,
explicit user, restricted permissions, graceful timeout, and persistent state
directories. Provide a container example only after native dependency pinning
works; mount YAML and state explicitly and never bake Telegram credentials or
sessions into images.

One account instance equals one service/container. Do not horizontally scale the
same TDLib directory.

## OPS-03: Backup, recovery, and retention

**Depends on:** DB-06, MED-02.

Implement an operator-triggered consistent SQLite backup and a manifest of media
hashes. Document whether TDLib session backup is supported only while stopped.
Test restoration into an isolated path before calling backup complete.

Retention policy must distinguish evidence tables, raw objects, audit records,
and downloaded files. Deletion is explicit, previewable, auditable, and scoped;
message `is_deleted` from Telegram is not a local retention command.

## OPS-04: Compliance documentation

**Depends on:** SEC-02.

Document authorized-use requirements, Telegram API-ID handling, privacy and
visibility limitations, account-ban/rate-limit risk, data minimization,
retention responsibilities, and Telegram API terms. Make clear that API-derived
data must not be used contrary to Telegram's content licensing and AI-scraping
terms.

