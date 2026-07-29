import asyncio
from pathlib import Path

from telegram_osint.collector import Collector
from telegram_osint.config import load_config
from telegram_osint.jobs import JobRunner
from telegram_osint.plugins import OutboxDispatcher
from telegram_osint.storage import Database


class FakeTelegram:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def request(self, request: dict[str, object], *, timeout: float = 60):
        self.requests.append(request)
        if request["@type"] == "getUser":
            return {
                "@type": "user",
                "id": str(request["user_id"]),
                "first_name": "Grace",
                "last_name": "Hopper",
                "usernames": {"active_usernames": ["grace"]},
            }
        if request["@type"] == "getUserFullInfo":
            return {"@type": "userFullInfo", "bio": {"text": "Compiler pioneer"}}
        if request["@type"] == "getUserProfilePhotos":
            offset = request["offset"]
            return {
                "@type": "chatPhotos",
                "total_count": 2,
                "photos": [{"id": "10"}, {"id": "11"}] if offset == 0 else [],
            }
        raise AssertionError(request)


class FakeHistoryTelegram:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def request(self, request: dict[str, object], *, timeout: float = 60):
        self.requests.append(request)
        if request["@type"] != "getChatHistory":
            raise AssertionError(request)
        if request["from_message_id"] == 0:
            return {
                "@type": "messages",
                "messages": [
                    {
                        "id": 10,
                        "chat_id": "-10042",
                        "date": 100,
                        "content": {
                            "@type": "messageText",
                            "text": {"text": "newer"},
                        },
                    },
                    {
                        "id": 9,
                        "chat_id": "-10042",
                        "date": 90,
                        "content": {
                            "@type": "messageText",
                            "text": {"text": "older"},
                        },
                    },
                ],
            }
        return {"@type": "messages", "messages": []}


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "account.yaml"
    path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths: {tdlib: td, database: data.sqlite3, media: media}
targets: {}
""",
        encoding="utf-8",
    )
    return path


def test_user_scrape_job_collects_full_info_and_all_visible_photos(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        config = load_config(_config(tmp_path))
        database = Database(config.paths.database)
        database.migrate()
        job_id = database.enqueue_job(
            kind="user_scrape",
            payload={"user_id": 42, "photos": "all_visible_history"},
        )
        telegram = FakeTelegram()
        runner = JobRunner(
            telegram=telegram,
            collector=Collector(account_id=1, config=config, database=database),
            database=database,
            account_id=1,
        )

        assert await runner.run_once() is True

        assert database.get_job(job_id).state == "succeeded"
        assert database.connection.execute(
            "SELECT COUNT(*) FROM user_full_info"
        ).fetchone()[0] == 1
        assert database.connection.execute(
            "SELECT COUNT(*) FROM user_photos"
        ).fetchone()[0] == 2

    asyncio.run(scenario())


def test_outbox_delivers_each_event_once_per_plugin(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.sqlite3")
    database.migrate()
    database.enqueue_outbox("example", {"value": 7})
    seen: list[dict[str, object]] = []
    dispatcher = OutboxDispatcher(
        database=database,
        plugins={"capture": lambda event: seen.append(event)},
    )

    dispatcher.dispatch()
    dispatcher.dispatch()

    assert [item["payload"]["value"] for item in seen] == [7]


def test_history_job_pages_until_exhausted_and_persists_messages(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        config_path = _config(tmp_path)
        config_path.write_text(
            config_path.read_text().replace(
                "targets: {}",
                """
targets:
  "-10042":
    history: {enabled: true}
    realtime: {enabled: true}
""",
            )
        )
        config = load_config(config_path)
        database = Database(config.paths.database)
        database.migrate()
        job_id = database.enqueue_job(
            kind="chat_history",
            payload={"chat_id": -10042, "from_message_id": 0},
            deduplication_key="history:-10042",
        )
        runner = JobRunner(
            telegram=FakeHistoryTelegram(),
            collector=Collector(account_id=1, config=config, database=database),
            database=database,
            account_id=1,
        )

        await runner.run_once()

        assert database.get_job(job_id).state == "succeeded"
        assert database.get_message(1, -10042, 10) is not None
        assert database.get_message(1, -10042, 9) is not None

    asyncio.run(scenario())
