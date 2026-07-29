# Telegram profile data available to an authorized user client

Research date: 2026-07-29. Sources are limited to Telegram's official TDLib and
MTProto API documentation.

## Recommended API boundary

Use TDLib as the default collector. It supplies the same account-scoped Telegram
data through a stable, stateful client API, keeps peer state locally, emits
ordered updates, and handles file transfers. Keep raw MTProto behind an optional
adapter only if a field or query that TDLib does not expose becomes a proven
requirement. Raw MTProto does not bypass Telegram privacy or membership rules.

TDLib expects applications to maintain caches from `updateUser`, `updateNewChat`,
and related updates. Telegram explicitly says updates and responses must be
processed in order; `updateUser` arrives before a newly discovered user ID is
used elsewhere. Therefore, metadata persistence should be update-driven rather
than implemented as periodic full-account scraping
([TDLib: handling updates](https://core.telegram.org/tdlib/getting-started#handling-updates)).

## User profile surface

### Base user record

TDLib's `user` object can expose:

- stable user ID, first and last name;
- username sets;
- phone number, when visible to the authenticated account;
- online/last-seen status;
- current profile-photo summary;
- name/profile accent colors, background custom emoji, emoji status;
- contact, mutual-contact, and close-friend flags;
- verification, Premium, support-account, and restriction information;
- active-story state;
- whether new chats are restricted, paid-message Stars, access status;
- user type, language code, and attachment-menu status.

The authoritative field list is the
[`user` TDLib object](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1user.html).
The `have_access` flag is important: if false, only the fields already present in
the object are known and the user ID cannot be passed to other TDLib methods.

`usernames` is not a single string. It separates ordered active usernames,
disabled usernames, an editable username, and collectible usernames
([TDLib `usernames`](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1usernames.html)).
Store each username as a child row with kind, position, and observation time.

### Full user record

`getUserFullInfo(user_id)` returns `userFullInfo`
([method](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1get_user_full_info.html)).
The current TDLib object includes, when known or applicable:

- personal, main, and public-fallback profile photos;
- block-list relationship and call/video-call capabilities;
- privacy-derived flags for calls, forwarded-message links, and voice/video notes;
- whether the user posted profile stories and enabled sponsored messages;
- contact phone-sharing exception requirements;
- bio and birthday;
- personal channel ID;
- displayed gift count/settings and bot-provided verification;
- groups-in-common count;
- inbound and outbound paid-message amounts;
- selected main profile tab and first profile audio;
- rating and pending rating;
- the current account's private contact note;
- Telegram Business information and bot information.

See the live
[`userFullInfo` field reference](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1user_full_info.html).
Many fields are nullable or explicitly “unknown”; absence must not be represented
as a confirmed empty value. Persist a value-state such as `known`, `empty`, or
`unknown`, plus the raw object and observation timestamp.

Raw MTProto's
[`userFull`](https://core.telegram.org/constructor/userFull)
can expose lower-level additions such as a personal-channel preview message and
some business/gift/payment fields. That is a useful compatibility escape hatch,
but not a reason to make MTProto the primary backend.

## Profile-photo history and downloads

TDLib provides `getUserProfilePhotos(user_id, offset, limit)`. `offset` must be
non-negative and each page is capped at 100 photos
([TDLib method](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1get_user_profile_photos.html)).
Iterate until the returned collection is exhausted. The analogous raw method,
[`photos.getUserPhotos`](https://core.telegram.org/method/photos.getUserPhotos),
supports `offset`, `max_id`, and `limit`, and can return a total count.

Important completeness limits:

- TDLib explicitly excludes the contact-specific personal photo and the public
  fallback photo from profile-photo history. Capture those separately from
  `userFullInfo`.
- “All history” means all photos Telegram returns to this authenticated account
  at collection time. Privacy settings, access loss, deleted photos, and expired
  file references prevent any claim of universal or permanent completeness.
- Deduplicate by Telegram photo/file identity, not offset. Offsets shift when a
  user changes photos.

Each `chatPhoto`/photo size contains TDLib file objects. Download selected files
with `downloadFile`; progress and completion arrive through `updateFile`
([TDLib `downloadFile`](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1download_file.html)).
Record photo ID, size variant, Telegram file IDs, dimensions, timestamps where
available, local path, content hash, download status, and last error. Do not put
image blobs in SQLite.

A suitable per-target YAML policy is:

```yaml
profile_collection:
  enabled: true
  snapshot_on_change: true
  photos:
    mode: all_visible_history # off | current | all_visible_history
    download: true
    max_bytes: 20971520
```

The collector should persist the resolved policy and config hash with each run.

## Status, privacy, stories, and visibility

User status is a tagged value: empty, online, offline with exact timestamp, or
privacy-coarsened “recently”, “last week”, and “last month”
([Telegram `UserStatus`](https://core.telegram.org/type/UserStatus)).
Never convert approximate states to invented timestamps. Store the status kind,
the exact timestamp only when supplied, and observed-at time. TDLib exposes
status changes separately as `updateUserStatus`.

The `active_story_state` field only indicates the user's active-story state; it
does not promise unrestricted access to story content. Story objects and updates
are available through TDLib's story functions/update types, but collection is
still scoped to stories visible to the logged-in account
([TDLib class index](https://core.telegram.org/tdlib/docs/classes.html)).
Archived or expired stories should not be assumed retrievable.

`getUserPrivacySettingRules` concerns the authenticated account's own privacy
settings. It is not an endpoint for reading another person's private rules.
For other users, persist only the observable results TDLib supplies—for example,
hidden phone number, coarse last-seen category, public fallback photo, or
call/forward restrictions—and label them as observations, not the user's rules.

## Group and channel membership

For supergroups/channels, first inspect `supergroupFullInfo.can_get_members`.
TDLib's `getSupergroupMembers` works only when that flag is true; some filters
also require administrator rights. It supports filters, offset pagination, and
at most 200 results per call
([TDLib method](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1get_supergroup_members.html)).

Each returned `chatMember` can contain a user-or-chat member ID, tag/custom
administrator title, inviter/promoter/banner ID when known, join/promotion/ban
timestamp, and a typed membership status
([TDLib `chatMember`](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1chat_member.html)).
Store observations/snapshots because roles and membership change.

The raw equivalent,
[`channels.getParticipants`](https://core.telegram.org/method/channels.getParticipants),
uses filter, offset, limit, and hash. Telegram documents `CHANNEL_PRIVATE` and
`CHAT_ADMIN_REQUIRED` errors, so even a joined account may be unable to enumerate
a complete member list. Channels are especially restrictive: Telegram describes
channels as allowing only administrators to see the member list
([TDLib `supergroup`](https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1supergroup.html)).

Consequently:

- call the result “visible members,” not “all members”;
- record filter, page cursor/offset, start/end times, expected count if known,
  returned count, completeness state, and terminal error;
- do not infer that an absent user left unless a complete comparable snapshot or
  an explicit membership update supports that conclusion;
- separately persist message authors encountered in history, because they may
  not appear in the currently visible participant list.

## Pagination, rate limits, and access failures

Telegram does not publish a universal requests-per-second allowance. MTProto
returns `FLOOD_WAIT_X` or `FLOOD_PREMIUM_WAIT_X`, where `X` is the required wait;
clients must honor it
([Telegram error handling](https://core.telegram.org/api/errors#420-flood)).
Use one scheduler per account, bounded concurrency, persisted cursors, jittered
retry for transient server failures, and exact server-directed waiting for
flood errors. Treat privacy/access errors as terminal for that item until account
or membership state changes.

Avoid frequent refetching of unchanged full profiles. Telegram's MTProto update
documentation says full peer information is not bundled with every update and
that peer data should be cached and updated reactively to avoid overloading the
server
([`updateUser`](https://core.telegram.org/constructor/updateUser)).

## Storage implications

Use separate latest-state and observation/history tables:

- `users` and `user_full_info` for the current normalized state;
- `user_profile_observations` for change-triggered snapshots;
- `user_usernames` for multi-valued username history;
- `user_status_observations` for exact/coarse status observations;
- `user_photos` and `user_photo_files` for photo identity, variants, and files;
- `chat_member_observations` and `member_scan_runs` for membership evidence;
- a raw JSON column or raw-object table keyed by schema/API version.

Schema fields must be nullable and version-tolerant because Telegram adds fields
and because “not returned” often means inaccessible or unknown, not false.
Snapshot only when canonical normalized content changes, while retaining
observed-at/first-seen/last-seen timestamps.

## Compliance boundary

Telegram requires each application to obtain its own `api_id`, protect user
privacy, avoid actions without the user's knowledge and consent, and comply with
its Content Licensing and AI Scraping terms. Telegram specifically prohibits
using API-derived data for training or developing AI/ML systems
([Telegram API Terms of Service](https://core.telegram.org/api/terms)).
The product should make account authorization explicit, encrypt session and
collected sensitive data, provide retention/deletion controls, and log who
enabled each collection target.
