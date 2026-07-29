# 11 — Delivery Roadmap

## Dependency spine

```text
Foundation
  -> domain contracts
  -> TDLib adapter + SQLite
  -> daemon + IPC + config
  -> entity/update persistence
  -> chat discovery
  -> live messages + history
  -> profiles + media
  -> plugins
  -> operational hardening
```

Build vertical tracer bullets. Avoid implementing every table before one real
update can travel from TDLib to SQLite and back through the CLI.

## Phase 0 — Decisions and reproducible foundation

**Tasks:** FND-01 through FND-04; ADRs listed in the scope document.

**Deliverable:** installable skeleton that reproducibly loads pinned
`libtdjson`, runs CI, and defines stable domain contracts.

**Exit gate:** clean environment setup and native smoke test pass on the first
supported platform.

## Phase 1 — Single-account authenticated daemon

**Tasks:** CFG-01/02, TDL-01/02, DB-01, DMN-01, IPC-01, minimal CLI status/auth.

**Deliverable:** foreground daemon starts, authenticates by QR or supported
fallback, survives restart using TDLib state, serves multiple local CLI clients,
and shuts down cleanly.

**Exit gate:** manual authorized test-account authentication runbook passes;
two daemon processes cannot open the same instance.

## Phase 2 — First end-to-end persisted update

**Tasks:** DB-02/03, COL-01, minimal DB writer and raw-object capture.

**Deliverable:** a live message traverses TDLib, normalization, transactional
SQLite persistence, and a CLI read query.

**Exit gate:** duplicate replay is idempotent, unknown fields remain in raw JSON,
and crash recovery loses no acknowledged checkpoint.

## Phase 3 — Chat selection and reliable collection

**Tasks:** CFG-03, CLI-01, DB-05, COL-02 through COL-06.

**Deliverable:** list joined chats, add multiple YAML targets via CLI, collect
real-time events, backfill selected histories, observe unlimited edits, and mark
deletions.

**Exit gate:** history/live race and repeated kill/restart tests converge on the
same database; flood-wait scheduler behavior is verified.

## Phase 4 — Profiles, membership, and media

**Tasks:** DB-04, PRF-01 through PRF-04, MED-01/02.

**Deliverable:** explicit `users scrape`, normalized/latest profile information,
change observations, optional all-visible profile-photo history, visible member
scans, and per-chat media downloads.

**Exit gate:** privacy-limited/unknown values are represented correctly; file
storage passes integrity, traversal, interruption, and disk-full tests.

## Phase 5 — Plugins and data access

**Tasks:** PLG-01 through PLG-04, DB-06.

**Deliverable:** stable plugin SDK, transactional outbox, isolated plugin
failures, reference plugins, and safe read/export interfaces.

**Exit gate:** replay and at-least-once tests pass; a broken plugin cannot raise
core receive-to-commit latency beyond the configured queue boundary.

## Phase 6 — Production hardening

**Tasks:** SEC-01/02, OPS-01 through OPS-04, all validation gates.

**Deliverable:** permissions, audits, redaction, health, systemd/container
examples, backup/recovery, retention, compliance docs, benchmarks, and soak
evidence.

**Exit gate:** correctness, performance, security, and recovery gates in
`10-testing-and-validation.md` pass with release evidence archived.

## Task execution template

Every implementation ticket derived from this plan must include:

1. task ID and exact dependency IDs;
2. user-visible outcome;
3. contract/schema changes;
4. failure modes and privacy implications;
5. tests written with the change;
6. migrations and rollback/recovery notes;
7. documentation update;
8. measurable acceptance criteria.

Keep changes small enough that each commit leaves the daemon buildable and the
database migratable. Schema migrations, domain contracts, and their tests belong
in the same change; do not land consumers before their contract.

## Recommended first ten implementation tickets

1. **FND-01:** Python package, tooling, and CI baseline.
2. **FND-02:** pinned `libtdjson` build/load smoke test.
3. **FND-03:** domain envelope and known/empty/unknown model.
4. **CFG-01:** versioned YAML parser and example.
5. **DB-01:** SQLite connection policy and migration runner.
6. **TDL-01:** fakeable JSON adapter with receiver thread.
7. **TDL-02:** authorization state machine.
8. **IPC-01:** versioned Unix-socket request/status path.
9. **DMN-01:** foreground lifecycle and clean shutdown.
10. **COL-01:** persist the first update-driven user/chat entity.

