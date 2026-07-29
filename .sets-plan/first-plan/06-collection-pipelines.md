# 06 — Collection Pipelines

## COL-01: Update-driven entity cache

**Depends on:** TDL-01, DB-02.

Consume TDLib user, chat, group, file, and authorization updates in receive
order. Persist raw input and normalized latest state in one logical operation.
Unknown fields remain in raw JSON. Cache only as an optimization; SQLite is the
recoverable application state and TDLib remains its own protocol cache.

**Tests:** recorded update sequences; new fields; duplicate updates; entity
arrives before/after referencing message; restart reconstruction.

## COL-02: Joined-chat discovery

**Depends on:** COL-01, CLI-01.

Page through TDLib chat lists until the desired list is loaded. Present stable
chat ID, type, title, usernames, unread counts where useful, accessibility, and
current target policies. Refresh discovery on chat-position/title updates.

Distinguish joined, archived, left, inaccessible, and forum/topic states where
TDLib exposes them. Listing a chat does not activate history or media downloads.

**Acceptance:** `chats list --json` is stable for scripting and handles thousands
of chats using pagination.

## COL-03: Target reconciliation

**Depends on:** CFG-02, COL-02, DB-05.

Diff every valid configuration version against active target runtime state:

- newly enabled history creates/resumes a backfill job;
- newly enabled real-time activates routing immediately;
- disabling prevents new scheduled work but preserves stored evidence;
- media/profile policy changes affect future work and optionally create an
  explicit reconciliation job;
- removal cancels target-scoped queued work after checkpointing.

Record applied config hash on jobs and collection runs so results can be traced
to policy.

## COL-04: Resumable history backfill

**Depends on:** COL-03, DB-03.

Fetch message history in bounded pages using stable message IDs/cursors. Persist
each page transactionally with its next checkpoint. Continue until the configured
boundary or Telegram exhaustion. Support optional oldest/newest dates later
without changing the base job contract.

Handle inaccessible messages, migrated groups, topics, empty pages, duplicates,
edits encountered during backfill, and target removal. Run at lower priority
than live updates. Do not infer that Telegram history is complete when an API
error or permission boundary ended the scan.

**Acceptance:** kill the daemon at every page boundary and mid-write; restart
produces the same final database as an uninterrupted run.

## COL-05: Real-time message ingestion

**Depends on:** COL-01, DB-03, COL-03.

Route selected-chat updates for new messages, content changes, edits, deletions,
interaction/reaction changes, pins, and relevant service actions. Normalize all
supported content variants and preserve unsupported raw variants.

Persist a live update before triggering plugins. When an update references an
unknown message, create a partial identity row and schedule a bounded repair
query if Telegram supports it. Multi-message deletions mark each known message.

Measure receive-to-commit latency and queue depth. Explicitly test messages
arriving while history backfill processes the same ID.

## COL-06: Rate control, retries, and checkpoints

**Depends on:** DB-05, TDL-01.

Use one account-level scheduler with operation-class concurrency limits. Honor
Telegram flood waits exactly, use bounded exponential retry with jitter for
transient transport/server errors, and classify privacy/access errors as
terminal until relevant state changes.

Store retry classification, Telegram error code/message, attempt count, and next
eligible time. Never tight-loop an unknown error. Add circuit breakers for disk,
database, and repeated native failures.

