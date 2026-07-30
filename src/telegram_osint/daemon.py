from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any

from telegram_osint.collector import Collector
from telegram_osint.config import AppConfig, load_config, mutate_config
from telegram_osint.ipc import ControlServer
from telegram_osint.jobs import JobRunner
from telegram_osint.storage import Database
from telegram_osint.telethon_adapter import TelethonAdapter

LOGGER = logging.getLogger(__name__)


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: Any | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self._file.close()
            self._file = None
            raise RuntimeError("another daemon owns this account instance") from error
        self._file.seek(0)
        self._file.truncate()
        self._file.write(str(os.getpid()))
        self._file.flush()

    def release(self) -> None:
        if self._file is not None:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None


class Daemon:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.database = Database(config.paths.database)
        self.account_id = 0
        self.collector = Collector(
            account_id=self.account_id,
            config=config,
            database=self.database,
        )
        self.client = TelethonAdapter(
            session_path=config.paths.session,
            api_id=config.account.api_id,
            api_hash=config.account.api_hash,
        )
        self.control = ControlServer(
            config=config,
            database=self.database,
            account_id=self.account_id,
            extra_handler=self._control,
        )
        self.lock = InstanceLock(config.paths.session.parent / ".session-conversion.lock")
        self.stop_event = asyncio.Event()
        self.job_runner = JobRunner(
            telegram=self.client,
            collector=self.collector,
            database=self.database,
            account_id=self.account_id,
        )
        self._job_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        self.lock.acquire()
        try:
            self.config.paths.media.mkdir(parents=True, exist_ok=True)
            self._ensure_session()
            self.database.migrate()
            await self.client.connect()
            # Register handlers immediately after connecting so updates arriving
            # during identity/dialog discovery are not lost.
            self.client.subscribe(self.collector.handle_update)
            me = await self.client.get_me()
            if me is None:
                raise RuntimeError(
                    "Telethon session is not authenticated; run "
                    "`tg-osint --config "
                    f"{self.config.source} session login-qr`"
                )
            self.account_id = int(me.id)
            self.collector.account_id = self.account_id
            self.control.account_id = self.account_id
            self.job_runner.account_id = self.account_id
            self.database.register_account(self.account_id, self.config.account.name)
            await self._discover_dialogs()
            await self.control.start()
            for chat_id, target in self.config.targets.items():
                if target.history_enabled:
                    self.database.enqueue_job(
                        kind="chat_history",
                        payload={"chat_id": chat_id, "from_message_id": 0},
                        deduplication_key=f"history:{chat_id}",
                    )
            self._job_task = asyncio.create_task(self._run_jobs())
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self.stop_event.set)
                except NotImplementedError:
                    pass
            LOGGER.info("daemon ready for account %s", self.config.account.name)
            await self.stop_event.wait()
        finally:
            await self.shutdown()

    def _ensure_session(self) -> None:
        if not self.config.paths.session.is_file():
            raise RuntimeError(
                "Telethon session is missing; run "
                "`tg-osint session import-tdata` first"
            )

    async def _discover_dialogs(self) -> None:
        async for chat in self.client.dialogs():
            self.database.upsert_chat(
                account_id=self.account_id,
                chat_id=int(chat["id"]),
                title=str(chat["title"]),
                chat_type=str(chat["type"]),
                username=chat.get("username"),
                raw=chat,
                observed_at=int(time.time()),
            )

    async def shutdown(self) -> None:
        if self._job_task is not None:
            self._job_task.cancel()
            try:
                await self._job_task
            except asyncio.CancelledError:
                pass
        await self.control.close()
        try:
            await self.client.disconnect()
        finally:
            self.database.close()
            self.lock.release()

    async def _run_jobs(self) -> None:
        while True:
            worked = await self.job_runner.run_once()
            if not worked:
                await asyncio.sleep(0.25)

    def _control(self, command: str, arguments: dict[str, Any]) -> Any:
        if command == "auth.status":
            return {"state": "authorizationStateReady", "backend": "telethon"}
        if command == "targets.list":
            return {
                str(chat_id): {
                    "history": target.history_enabled,
                    "realtime": target.realtime_enabled,
                    "media": target.media.enabled,
                }
                for chat_id, target in self.config.targets.items()
            }
        if command in {"targets.add", "targets.remove", "targets.media"}:
            operation = {
                "targets.add": "target_add",
                "targets.remove": "target_remove",
                "targets.media": "target_media",
            }[command]
            updated = mutate_config(
                self.config.source,
                expected_hash=str(arguments["expected_hash"]),
                operation=operation,
                arguments=arguments,
            )
            self.config = updated
            self.collector.config = updated
            self.control.config = updated
            if command == "targets.add":
                chat_id = int(arguments["chat_id"])
                self.database.enqueue_job(
                    kind="chat_history",
                    payload={"chat_id": chat_id, "from_message_id": 0},
                    deduplication_key=f"history:{chat_id}",
                )
            return {"config_hash": updated.config_hash}
        raise ValueError(f"unknown command: {command}")


def run_daemon(config_path: str | Path) -> None:
    config = load_config(config_path)
    asyncio.run(Daemon(config).run())
