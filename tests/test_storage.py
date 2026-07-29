from pathlib import Path

from telegram_osint.domain import MessageEvent, MessageRevision
from telegram_osint.storage import Database


def test_message_revisions_are_unbounded_and_deletion_preserves_them(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "collector.sqlite3")
    database.migrate()

    for sequence, text in enumerate(("first", "second", "third"), start=1):
        database.persist_message(
            MessageRevision(
                account_id=1,
                chat_id=-10042,
                message_id=7,
                revision_sequence=sequence,
                observed_at=1_700_000_000 + sequence,
                text=text,
                raw={"@type": "message", "id": 7, "content": text},
            ),
            MessageEvent.CREATED if sequence == 1 else MessageEvent.EDITED,
        )
    database.mark_deleted(
        account_id=1,
        chat_id=-10042,
        message_id=7,
        observed_at=1_700_000_100,
    )

    message = database.get_message(1, -10042, 7)
    assert message is not None
    assert message["is_deleted"] == 1
    assert [row["text"] for row in message["revisions"]] == [
        "first",
        "second",
        "third",
    ]


def test_replaying_same_revision_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "collector.sqlite3")
    database.migrate()
    revision = MessageRevision(
        account_id=1,
        chat_id=-10042,
        message_id=7,
        revision_sequence=1,
        observed_at=1_700_000_000,
        text="hello",
        raw={"@type": "message", "id": 7},
    )

    database.persist_message(revision, MessageEvent.CREATED)
    database.persist_message(revision, MessageEvent.CREATED)

    assert len(database.get_message(1, -10042, 7)["revisions"]) == 1


def test_durable_job_can_be_claimed_and_completed(tmp_path: Path) -> None:
    database = Database(tmp_path / "collector.sqlite3")
    database.migrate()
    job_id = database.enqueue_job(
        kind="user_scrape",
        payload={"user_id": 42, "photos": "current"},
        deduplication_key="user:42",
    )

    job = database.claim_next_job()
    assert job is not None
    assert job.id == job_id
    assert job.payload["user_id"] == 42

    database.complete_job(job_id)
    assert database.get_job(job_id).state == "succeeded"


def test_migration_recovers_interrupted_running_job(tmp_path: Path) -> None:
    path = tmp_path / "collector.sqlite3"
    database = Database(path)
    database.migrate()
    job_id = database.enqueue_job(kind="history", payload={"cursor": 10})
    database.claim_next_job()
    database.close()

    recovered = Database(path)
    recovered.migrate()

    assert recovered.get_job(job_id).state == "queued"
