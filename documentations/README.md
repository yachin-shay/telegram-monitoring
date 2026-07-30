# Telegram OSINT Collector Documentation

This directory documents the authorized Telegram collection tool in this
repository. The project runs one foreground daemon per Telegram account. It
uses Telethon for API access, OpenTele2 only for importing an existing
Telegram Desktop `tdata` profile, and SQLite for durable collection state.

## Recommended reading order

1. [Architecture](01-architecture.md)
2. [Installation and authentication](02-installation-and-authentication.md)
3. [Configuration](03-configuration.md)
4. [Running and operating the daemon](04-running-and-operations.md)
5. [Collection pipelines](05-collection-pipelines.md)
6. [SQLite data model](06-data-model.md)
7. [Plugins and extension points](07-plugins-and-extension-points.md)
8. [Troubleshooting and security](08-troubleshooting-and-security.md)

The implementation plan that motivated the project remains in
`.sets-plan/first-plan/`. These documents describe the current Telethon
implementation rather than the superseded TDLib runtime design.

## Scope and authorization

The collector is intended for accounts and chats that the operator is
authorized to access. It does not bypass Telegram privacy controls, discover
messages unavailable to the authenticated account, or guarantee recovery of
deleted content. Protect session files, API credentials, databases, media, and
logs as sensitive data.
