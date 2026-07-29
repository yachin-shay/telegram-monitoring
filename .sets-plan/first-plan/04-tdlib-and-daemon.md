# 04 — TDLib and Daemon

## TDL-01: Thin native JSON adapter

**Depends on:** FND-02, FND-03.

Bind the current `td_create_client_id`, `td_send`, `td_receive`, and `td_execute`
C functions using a narrow foreign-function layer. Keep all pointer conversion,
UTF-8 handling, JSON parsing, and native errors in this module.

Use one receiver thread. Attach a unique `@extra` correlation key to every
request and resolve asyncio futures on responses. Route objects without a known
correlation key as updates. Preserve receive order and capture unknown object
types rather than crashing.

**Tests:** fake native library; response correlation; timeouts; cancellation;
out-of-order responses; ordered updates; invalid UTF-8/JSON handling; shutdown.

## TDL-02: Authorization state machine

**Depends on:** TDL-01.

Implement every TDLib authorization state explicitly: parameters, database
encryption key, phone number, QR confirmation, authentication code, email code
where required, 2FA password, ready, logging out, closing, and closed.

Never accept passwords through process arguments. QR payloads and interactive
secrets are returned only to an authenticated local CLI client and redacted from
logs. Persist no raw password or login code.

**Acceptance:** new QR login, phone-code fallback, 2FA, restart with an existing
session, logout, revoked session, and wrong-code recovery are integration-tested
against a manual test account runbook.

## DMN-01: Foreground daemon lifecycle

**Depends on:** CFG-02, TDL-01, DB-01.

Startup sequence:

1. parse flags and load/validate YAML;
2. acquire an account-instance lock;
3. validate directories and permissions;
4. migrate and integrity-check SQLite;
5. load TDLib and start authorization;
6. bind the Unix socket;
7. recover durable jobs;
8. enter ready or authentication-required state.

Shutdown sequence stops accepting mutations, cancels or checkpoints jobs,
drains core persistence, closes TDLib and waits for the closed state, checkpoints
SQLite WAL if safe, removes the socket, and releases the instance lock.

Use non-zero exit codes for configuration, native dependency, database, and
authorization failures. Foreground operation means no fork, PID-file daemonizer,
or hidden background process.

## IPC-01: Local control protocol

**Depends on:** FND-03.

Create a versioned newline-delimited JSON protocol over a Unix domain socket.
Frame limits prevent memory abuse. Requests contain protocol version, request
ID, command, arguments, expected config hash, and client metadata. Responses
contain status, typed result/error, active config hash, and optional stream ID.

Restrict socket directory and file permissions to the account owner. On Linux,
verify peer credentials where available. Support streaming job progress with a
bounded subscriber buffer; slow subscribers are disconnected without affecting
jobs.

**Tests:** protocol negotiation; partial frames; oversized frames; malformed
JSON; unauthorized peer; concurrent clients; daemon restart; stale socket.

