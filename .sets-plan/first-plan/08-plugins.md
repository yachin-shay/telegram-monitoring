# 08 — Pipelines and Plugins

## PLG-01: Stable plugin contract

**Depends on:** FND-03.

Define a versioned contract with plugin metadata, configuration validation,
lifecycle hooks, subscribed domain event types, and health status. Plugins
receive immutable normalized events and references to raw objects through a
read-only query interface.

Plugins must not receive the TDLib client, SQLite write connection, session
secrets, or unrestricted configuration mutation. Version one assumes plugins
installed by the operator are trusted Python code, but capability minimization
still reduces accidental coupling.

Discover plugins through Python entry points. Require unique name, contract
version range, package version, and declared subscriptions.

## PLG-02: Transactional outbox

**Depends on:** DB-03, PLG-01.

Core persistence writes an outbox event in the same transaction as collected
data. A dispatcher delivers committed events to plugins with per-plugin cursor,
attempt, and dead-letter tracking.

Delivery is at least once, so event IDs are stable and plugin authors must be
idempotent. A slow or failing plugin has a bounded queue and cannot stop TDLib
ingestion. Operators can pause, resume, replay, or skip poisoned events with an
audit record.

## PLG-03: Pipeline stage model

**Depends on:** PLG-01.

Keep the core ingestion pipeline fixed for correctness:

```text
receive -> normalize -> target policy -> core persistence -> committed outbox
```

Allow plugins after commit for export, notifications, indexing, enrichment, and
analytics. Do not permit arbitrary pre-persistence mutation in version one; it
would make forensic records dependent on plugin order.

If pre-commit filters are later required, define them as deterministic,
side-effect-free policy extensions with explicit ordering and audit hashes.

## PLG-04: Reference plugins and SDK

**Depends on:** PLG-02.

Ship two small reference plugins:

- JSON Lines exporter demonstrating replay and idempotency;
- keyword alert logger demonstrating filtered subscriptions without external
  messaging side effects.

Publish typed interfaces, fixture factories, a local plugin test harness,
compatibility rules, and packaging instructions. Validate plugin configuration
before daemon readiness.

**Acceptance:** plugin install/discovery, replay, crash, timeout, duplicate
delivery, incompatible version, invalid config, and removal are tested.

