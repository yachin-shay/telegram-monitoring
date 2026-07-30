import asyncio
from pathlib import Path

from telegram_osint.config import load_config
from telegram_osint.ipc import ControlClient, ControlServer
from telegram_osint.storage import Database


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "account.yaml"
    path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths:
  tdlib: td
  database: data.sqlite3
  media: media
  socket: daemon.sock
targets: {}
""",
        encoding="utf-8",
    )
    return path


def test_multiple_clients_control_one_daemon(tmp_path: Path) -> None:
    async def scenario() -> None:
        config = load_config(_config(tmp_path))
        database = Database(config.paths.database)
        database.migrate()
        server = ControlServer(config=config, database=database, account_id=1)
        await server.start()
        try:
            clients = [ControlClient(config.paths.socket) for _ in range(8)]
            statuses = await asyncio.gather(
                *(client.request("status", {}) for client in clients)
            )
            assert all(item["result"]["account"] == "test" for item in statuses)

            response = await clients[0].request(
                "users.scrape",
                {"user_id": 42, "photos": "all_visible_history"},
            )
            assert response["ok"] is True
            job_id = response["result"]["job_id"]
            job = await clients[1].request("jobs.show", {"job_id": job_id})
            assert job["result"]["payload"]["user_id"] == 42
        finally:
            await server.close()
            database.close()

    asyncio.run(scenario())


def test_missing_control_socket_explains_that_daemon_must_start(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        client = ControlClient(tmp_path / "missing.sock")
        try:
            await client.request("status", {})
        except ConnectionError as error:
            assert "start the daemon" in str(error)
        else:
            raise AssertionError("missing socket should fail")

    asyncio.run(scenario())
