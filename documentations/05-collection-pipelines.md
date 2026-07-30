# Collection pipelines

## Dialog discovery

After authentication, the daemon iterates Telethon dialogs and upserts each
joined chat into `chats`. The raw dialog metadata is retained as JSON. This
provides stable IDs and titles for selecting targets in YAML.

## Historical messages

For every target with `history.enabled`, startup inserts a deduplicated
`chat_history` job. The worker requests pages of up to 100 messages, normalizes
each message through the collector, then checkpoints the oldest processed
message ID. Empty pages terminate the job.

History and realtime paths share the same message storage contract, so a
message received live and later seen during backfill is idempotent.

## Realtime messages

The adapter subscribes to Telethon new-message, edited-message, and
message-deleted events. New and edited messages are normalized into the
collector’s update shape. The collector stores a revision rather than
overwriting the previous revision.

Deletion is represented by `messages.is_deleted = 1` and
`deleted_observed_at`; the original revisions remain available. This is
intentional: deletion is a state marker, not physical row removal.

## Profiles and user scraping

The `user-scrape USER_ID` command creates a durable `user_scrape` job. The
worker collects:

1. basic user data,
2. full-user information,
3. optionally all visible profile-photo metadata.

Profile changes are content-hashed. A changed observation is retained in
`user_profile_observations`, while the latest basic and full records are kept
in `users` and `user_full_info`.

## Media policy and current implementation boundary

Media policy is selected per chat. The configuration and `MediaStore` define
whether media is eligible, which media types are eligible, and the maximum
size. The current Telethon message normalization stores raw message metadata;
it does not yet automatically download every message attachment. A download
pipeline should call `MediaStore.finalize()` after an authorized Telethon
download and persist the resulting path/hash in a media table or plugin.

When finalized, files are content-addressed by SHA-256 under the media root:

```text
media/
  ab/
    cd/
      abcdef...sha256
```

The hash layout deduplicates identical downloads and makes integrity checks
straightforward. Files are finalized only when the source is a regular,
non-symlink file.

## Idempotence and failure

SQLite transactions surround message, profile, job, and outbox writes.
Duplicate revisions and duplicate events are ignored by uniqueness constraints.
Failed jobs retain their error text and increment attempt state; jobs are
requeued on daemon restart when necessary.

Telegram API rate limits and transient network failures should be monitored in
logs. The current worker boundary records failures durably; operators should
inspect job state before deciding whether to retry. Media downloading and
automatic retry/backoff remain extension points rather than guarantees of the
current daemon.
