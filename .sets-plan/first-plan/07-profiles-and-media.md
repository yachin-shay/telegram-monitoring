# 07 — Profiles and Media

## PRF-01: Explicit user enrichment

**Depends on:** COL-01, DB-04, CLI-01.

`users scrape USER_ID` submits a durable job. Resolve the user through data
already visible to TDLib, then request full info when `have_access` permits.
Persist base user, full-info, username collection, status kind, bio, birthday,
business/bot fields, relationship flags, and all currently documented fields
without treating missing as false.

Return a clear inaccessible/unknown result when TDLib cannot use the ID. Do not
attempt phone-number enumeration or access-control bypass.

The job accepts a temporary execution policy, while persistent recurring
behavior belongs in YAML. `--photos off|current|all-visible-history` controls
this job but does not modify YAML unless invoked through an explicit config
command.

## PRF-02: Profile observation history

**Depends on:** PRF-01.

Maintain latest state plus content-hash-deduplicated observations. Observe on
TDLib entity updates, explicit scrape, and configured refresh jobs. Store status
as its exact tagged category: exact timestamp only when Telegram supplies one;
otherwise keep coarse labels such as recently/last-week.

Store usernames as ordered, typed child rows because active, disabled,
collectible, and editable usernames are not one field. Record first-seen,
last-seen, and observation evidence without claiming the actual change time.

## PRF-03: Visible profile-photo history

**Depends on:** PRF-01, MED-01.

Implement modes:

- `off`: collect no photo history beyond incidental current metadata;
- `current`: persist current/personal/public-fallback photo metadata and
  optionally download;
- `all_visible_history`: paginate `getUserProfilePhotos` with pages no larger
  than 100, plus separately capture personal and public-fallback photos exposed
  by full info.

Deduplicate by Telegram photo/file identity, never page offset. Stop on
exhaustion, access loss, or classified error and record completeness. Download
selected size variants according to policy; prefer original/highest available
unless storage policy says otherwise.

## PRF-04: Visible member scans

**Depends on:** DB-04, COL-03.

Expose member scanning only when TDLib capability flags permit it. Paginate
supergroup members with supported filters and maximum 200 per request. Some
filters and channels require administrator rights; record that outcome instead
of retrying indefinitely.

Member-scan mode is per target: off, on-demand, or scheduled. Message authors are
persisted independently even if they are absent from a visible member list.
Deep-enriching all returned members is a separate explicit policy to control API
load.

## MED-01: Per-target media policy

**Depends on:** CFG-01, DB-04.

Resolve policy in this order: temporary job override, target-specific YAML,
application default. Store the resolved policy and config hash with every
download decision. Filters include enabled, Telegram content type, MIME allow
and deny patterns, maximum bytes, optional date bounds, and profile-photo mode.

Metadata is always persisted when observed even if downloading is disabled.
Policy denial is a completed decision, not a failed download.

## MED-02: Download and content-addressed storage

**Depends on:** MED-01, TDL-01.

Schedule TDLib `downloadFile` calls with bounded concurrency and consume
`updateFile` progress. Once complete:

1. verify expected size when available;
2. stream-hash the file;
3. move it atomically beneath the configured media root using a
   content-addressed path;
4. persist relative path, hash, size, and status;
5. deduplicate identical content while retaining all Telegram source links.

Never trust Telegram filenames as paths. Sanitize names for export only. Defend
against symlink traversal and a media root overlapping TDLib or database paths.

**Acceptance:** interrupted download recovery, duplicate content, disk-full,
oversize rejection, expired file reference refresh, and malicious filenames are
tested.

