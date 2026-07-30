# Installation and authentication

## Prerequisites

- Python 3.12 or newer.
- Telegram API ID and API hash from
  [my.telegram.org](https://my.telegram.org).
- An account that is authorized to access the chats being collected.
- `uv`.

## Create the virtual environment

The project convention is to use a local uv-managed environment:

```bash
uv venv --system-site-packages .venv
UV_CACHE_DIR=/tmp/telegram-monitoring-uv-cache \
  uv pip install --python .venv/bin/python -e .
```

The dependency set includes Telethon, TgCrypto, OpenTele2, PyYAML, and qrcode.
Do not install project dependencies with the system `pip`.

## Configure API credentials

Copy the example and provide the API hash through the environment:

```bash
cp config.example.yaml config.yaml
export TELEGRAM_API_HASH='replace-with-your-api-hash'
```

Set `account.api_id` to the numeric API ID. Keeping the hash in an environment
variable avoids putting it in shell history or committing it to YAML.

## Fresh QR login

Use the configured `paths.session` destination:

```bash
.venv/bin/tg-osint --config config.yaml session login-qr
```

Scan the terminal QR in Telegram at **Settings → Devices → Link Desktop
Device**. If Telegram requests a second-factor password, the command prompts
for it securely. The command exits with a JSON result containing the session
path, user ID, and username.

Do not run the daemon while login is in progress. Both operations use the
session lock.

## Import an existing Desktop profile

```bash
.venv/bin/tg-osint --config config.yaml session import-tdata \
  --tdata /secure/TelegramDesktop/tdata \
  --output state/research-1/account.session
```

The command prompts for the Telegram Desktop local passcode. Use `--force`
only when intentionally replacing an existing session. The source directory
must be a real directory, not a symlink, and the output cannot be inside it.

The imported session currently reuses the Telegram Desktop authorization
credential. Avoid simultaneously running Telegram Desktop and the daemon with
that imported credential.

## Verify before starting

```bash
.venv/bin/tg-osint --config config.yaml daemon
```

An unauthorized or revoked session now fails with an actionable error:

```text
Telethon session is not authenticated; run `tg-osint ... session login-qr`
```
