# Telethon session architecture

The collector now uses an existing Telegram Desktop profile as its
authentication input:

```text
Telegram Desktop tdata
        │
        │ OpenTele2, read-only
        ▼
Telethon SQLite session
        │
        ▼
TelethonAdapter → collector → SQLite/media/plugins
```

TDLib is not used by this runtime. TDLib’s `database_directory` is a separate
encrypted storage format and has no supported export to `tdata` or Telethon.
OpenTele2’s conversion boundary is Telegram Desktop `tdata` and Telethon
sessions, so the source is never interpreted as a TDLib database.

## Conversion

```bash
tg-osint --config config.yaml session import-tdata \
  --tdata /secure/TelegramDesktop/tdata \
  --output state/account.session
```

The command:

1. validates that the source is a real directory and not a symlink;
2. prompts for the local Telegram Desktop passcode without accepting it as an
   argument;
3. loads the profile through pinned OpenTele2;
4. writes a new session in a temporary sibling directory;
5. connects and calls `get_me()` to validate the generated session;
6. atomically renames the session into place with owner-only permissions.

The source profile is never modified. Do not open it in Telegram Desktop while
conversion is running. The output `.session` file is a bearer credential and
must be protected like the source `tdata`.

## Runtime ownership

The foreground daemon requires the generated session path to exist. It does not
silently convert profiles on startup. One daemon process owns one Telethon
session, one SQLite writer, and one Unix control socket.

