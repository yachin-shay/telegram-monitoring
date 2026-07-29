# 03 — Configuration and CLI

## CFG-01: Versioned YAML schema

**Depends on:** FND-03.

Define a strict, versioned document with sections for account paths, Telegram
credentials by secret reference, database, logging, IPC, scheduler limits,
plugins, and targets. A target is keyed by numeric chat ID and contains:

```yaml
schema_version: 1
account:
  name: research-1
  api_id_env: TELEGRAM_API_ID
  api_hash_env: TELEGRAM_API_HASH
paths:
  tdlib: ./state/research-1/tdlib
  database: ./state/research-1/collector.sqlite3
  media: ./state/research-1/media
targets:
  "-1001234567890":
    history: {enabled: true}
    realtime: {enabled: true}
    members: {mode: visible_on_demand}
    media:
      enabled: false
      types: [photo, video, document, audio, voice]
      max_bytes: 104857600
    profiles:
      enabled: true
      snapshot_on_change: true
      photos:
        mode: all_visible_history
        download: true
        max_bytes: 20971520
```

Validate path collisions, invalid IDs, impossible limits, duplicated plugin
names, and unsafe socket permissions. Unknown keys should fail by default so a
misspelling cannot silently disable collection.

**Tests:** valid examples; every validation branch; schema upgrade fixtures.

## CFG-02: Safe configuration loading and reload

**Depends on:** CFG-01.

Resolve relative paths against the YAML file directory. Resolve secrets at
runtime without writing secret values back. Compute a canonical configuration
hash. Watch using portable polling first; debounce changes and apply only a
fully parsed document.

Classify fields as hot-reloadable or restart-required. Target and policy changes
are hot; TDLib directory, database path, socket path, and account credentials
require restart. Surface a structured diff through daemon status.

**Done when:** malformed or partial YAML never replaces the active config and
operators can see which version is active.

## CFG-03: Atomic CLI mutation

**Depends on:** CFG-01, IPC-01.

Explicit management commands send mutations to the daemon. The daemon takes an
exclusive config lock, reloads the current file, applies a semantic mutation,
writes a same-directory temporary file, fsyncs it, validates it, and atomically
replaces the original. Preserve comments and unrelated formatting where the
chosen YAML library permits.

Prevent lost updates using the expected config hash supplied by the CLI. If the
file changed, reject with a conflict and show the operator how to retry.

Commands:

- `config validate`, `config show`, `config set`, `config export`;
- `targets add/remove/list`;
- `targets media CHAT_ID enable|disable`;
- `targets profiles CHAT_ID ...`.

Startup flags override the loaded object in memory and are never written.

## CLI-01: Multi-terminal command surface

**Depends on:** IPC-01.

Implement consistent text and `--json` output, stable exit codes, connection
timeouts, and command request IDs. Initial commands:

- `status`, `health`;
- `auth qr`, `auth phone`, `auth status`;
- `chats list/show`;
- `targets ...`;
- `users scrape USER_ID [--photos MODE]`;
- `jobs list/show/follow/cancel/retry`;
- `db info`;
- `plugins list/status`.

Every mutating command records actor, terminal/process metadata, request ID, old
config hash, and new config hash in the audit log.

**Acceptance:** two dozen concurrent CLI processes can issue read commands while
serialized mutations either succeed or return explicit conflicts.

