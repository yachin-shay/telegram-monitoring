from datetime import datetime, timezone
from pathlib import Path

from telegram_osint.collector import Collector
from telegram_osint.config import load_config
from telegram_osint.storage import Database
from telegram_osint.telethon_adapter import telethon_message_to_update


def test_telethon_message_normalizes_into_existing_collector_contract(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "account.yaml"
    config_path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths: {tdlib: td, database: data.sqlite3, media: media}
targets:
  "-10042": {history: {enabled: true}, realtime: {enabled: true}}
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    database = Database(config.paths.database)
    database.migrate()
    collector = Collector(account_id=42, config=config, database=database)

    update = telethon_message_to_update(
        chat_id=-10042,
        message_id=7,
        text="from telethon",
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        raw={"id": 7, "message": "from telethon"},
    )
    collector.handle_update(update)

    stored = database.get_message(42, -10042, 7)
    assert stored is not None
    assert stored["revisions"][0]["text"] == "from telethon"

