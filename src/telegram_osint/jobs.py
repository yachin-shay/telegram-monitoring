from __future__ import annotations

import time
import logging
from typing import Any, Protocol

from telegram_osint.collector import Collector
from telegram_osint.storage import Database

LOGGER = logging.getLogger(__name__)


class TelegramClient(Protocol):
    async def request(
        self,
        request: dict[str, Any],
        *,
        timeout: float = 60,
    ) -> dict[str, Any]: ...


class JobRunner:
    def __init__(
        self,
        *,
        telegram: TelegramClient,
        collector: Collector,
        database: Database,
        account_id: int,
    ) -> None:
        self.telegram = telegram
        self.collector = collector
        self.database = database
        self.account_id = account_id

    async def run_once(self) -> bool:
        job = self.database.claim_next_job()
        if job is None:
            return False
        LOGGER.info("job %s started kind=%s attempt=%s", job.id, job.kind, job.attempts + 1)
        self.database.update_job_progress(job.id, {"stage": "started"})
        try:
            if job.kind == "user_scrape":
                await self._user_scrape(job.id, job.payload)
            elif job.kind == "chat_history":
                await self._chat_history(job.id, job.payload)
            else:
                raise ValueError(f"unsupported job kind: {job.kind}")
        except Exception as error:
            self.database.fail_job(job.id, str(error))
            self.database.update_job_progress(
                job.id, {"stage": "failed", "error": str(error)}
            )
            LOGGER.error("job %s failed: %s", job.id, error)
        else:
            self.database.complete_job(job.id)
            self.database.update_job_progress(job.id, {"stage": "completed"})
            LOGGER.info("job %s completed", job.id)
        return True

    async def _user_scrape(self, job_id: str, payload: dict[str, Any]) -> None:
        user_id = int(payload["user_id"])
        self.database.update_job_progress(
            job_id, {"stage": "fetching_user", "user_id": user_id}
        )
        user = await self.telegram.request({"@type": "getUser", "user_id": user_id})
        self.collector.handle_update({"@type": "updateUser", "user": user})
        full_info = await self.telegram.request(
            {"@type": "getUserFullInfo", "user_id": user_id}
        )
        observed_at = int(time.time())
        self.database.persist_user_full_info(
            account_id=self.account_id,
            user_id=user_id,
            raw=full_info,
            observed_at=observed_at,
        )
        if payload.get("photos") != "all_visible_history":
            self.database.update_job_progress(job_id, {"stage": "user_complete"})
            return
        offset = 0
        while True:
            result = await self.telegram.request(
                {
                    "@type": "getUserProfilePhotos",
                    "user_id": user_id,
                    "offset": offset,
                    "limit": 100,
                }
            )
            photos = result.get("photos", [])
            for photo in photos:
                self.database.persist_user_photo(
                    account_id=self.account_id,
                    user_id=user_id,
                    photo_id=int(photo["id"]),
                    raw=photo,
                    observed_at=observed_at,
                )
            offset += len(photos)
            self.database.update_job_progress(
                job_id,
                {
                    "stage": "fetching_profile_photos",
                    "user_id": user_id,
                    "photos_seen": offset,
                    "photos_total": int(result.get("total_count", offset)),
                },
            )
            if not photos or offset >= int(result.get("total_count", offset)):
                break

    async def _chat_history(self, job_id: str, payload: dict[str, Any]) -> None:
        chat_id = int(payload["chat_id"])
        from_message_id = int(payload.get("from_message_id", 0))
        messages_seen = int(payload.get("messages_seen", 0))
        while True:
            result = await self.telegram.request(
                {
                    "@type": "getChatHistory",
                    "chat_id": chat_id,
                    "from_message_id": from_message_id,
                    "offset": -1 if from_message_id else 0,
                    "limit": 100,
                    "only_local": False,
                }
            )
            messages = result.get("messages", [])
            if not messages:
                return
            for message in messages:
                self.collector.handle_history_message(message)
            messages_seen += len(messages)
            next_id = min(int(message["id"]) for message in messages)
            if next_id == from_message_id:
                return
            from_message_id = next_id
            payload["from_message_id"] = from_message_id
            self.database.checkpoint_job(job_id, payload)
            self.database.update_job_progress(
                job_id,
                {"stage": "history_page", "messages_seen": messages_seen},
            )
