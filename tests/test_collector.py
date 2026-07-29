from pathlib import Path

from telegram_osint.collector import Collector
from telegram_osint.config import load_config
from telegram_osint.storage import Database


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "account.yaml"
    path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths: {tdlib: td, database: data.sqlite3, media: media}
targets:
  "-10042":
    history: {enabled: true}
    realtime: {enabled: true}
    media: {enabled: false}
""",
        encoding="utf-8",
    )
    return path


def test_collector_persists_only_targeted_live_messages(tmp_path: Path) -> None:
    config = load_config(_config(tmp_path))
    database = Database(config.paths.database)
    database.migrate()
    collector = Collector(account_id=1, config=config, database=database)

    collector.handle_update(
        {
            "@type": "updateNewMessage",
            "message": {
                "id": 8,
                "chat_id": "-10042",
                "date": 1_700_000_000,
                "content": {
                    "@type": "messageText",
                    "text": {"text": "collected", "entities": []},
                },
            },
        }
    )
    collector.handle_update(
        {
            "@type": "updateNewMessage",
            "message": {
                "id": 9,
                "chat_id": "-10077",
                "date": 1_700_000_001,
                "content": {
                    "@type": "messageText",
                    "text": {"text": "ignored", "entities": []},
                },
            },
        }
    )

    assert database.get_message(1, -10042, 8)["revisions"][0]["text"] == "collected"
    assert database.get_message(1, -10077, 9) is None


def test_collector_records_multiple_edits_and_deletion(tmp_path: Path) -> None:
    config = load_config(_config(tmp_path))
    database = Database(config.paths.database)
    database.migrate()
    collector = Collector(account_id=1, config=config, database=database)
    collector.handle_update(
        {
            "@type": "updateNewMessage",
            "message": {
                "id": 8,
                "chat_id": "-10042",
                "date": 100,
                "content": {"@type": "messageText", "text": {"text": "one"}},
            },
        }
    )
    for text, timestamp in (("two", 101), ("three", 102)):
        collector.handle_update(
            {
                "@type": "updateMessageContent",
                "chat_id": "-10042",
                "message_id": 8,
                "new_content": {
                    "@type": "messageText",
                    "text": {"text": text},
                },
                "edit_date": timestamp,
            }
        )
    collector.handle_update(
        {
            "@type": "updateDeleteMessages",
            "chat_id": "-10042",
            "message_ids": [8],
            "is_permanent": True,
        }
    )

    message = database.get_message(1, -10042, 8)
    assert [revision["text"] for revision in message["revisions"]] == [
        "one",
        "two",
        "three",
    ]
    assert message["is_deleted"] == 1


def test_collector_persists_chat_and_user_metadata(tmp_path: Path) -> None:
    config = load_config(_config(tmp_path))
    database = Database(config.paths.database)
    database.migrate()
    collector = Collector(account_id=1, config=config, database=database)

    collector.handle_update(
        {
            "@type": "updateNewChat",
            "chat": {
                "id": "-10042",
                "title": "Research",
                "type": {"@type": "chatTypeSupergroup"},
            },
        }
    )
    collector.handle_update(
        {
            "@type": "updateUser",
            "user": {
                "id": "42",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "usernames": {"active_usernames": ["ada"]},
            },
        }
    )

    assert database.list_chats(1)[0]["title"] == "Research"
    user = database.connection.execute(
        "SELECT * FROM users WHERE account_id = 1 AND user_id = 42"
    ).fetchone()
    assert user["username"] == "ada"
    observations = database.connection.execute(
        "SELECT COUNT(*) FROM user_profile_observations"
    ).fetchone()[0]
    assert observations == 1

