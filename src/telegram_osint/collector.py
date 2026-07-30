from __future__ import annotations

import time
from typing import Any

from telegram_osint.config import AppConfig
from telegram_osint.domain import MessageEvent, MessageRevision
from telegram_osint.storage import Database


class Collector:
    """Normalize TDLib updates into durable account-scoped observations."""

    def __init__(
        self,
        *,
        account_id: int,
        config: AppConfig,
        database: Database,
    ) -> None:
        self.account_id = account_id
        self.config = config
        self.database = database

    def handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("@type")
        if update_type == "updateNewMessage":
            self._new_message(update["message"])
        elif update_type == "updateMessageContent":
            self._edit_message(update)
        elif update_type == "updateDeleteMessages":
            self._delete_messages(update)
        elif update_type == "updateNewChat":
            self._chat(update["chat"])
        elif update_type == "updateUser":
            self._user(update["user"])

    def _is_realtime_target(self, chat_id: int) -> bool:
        target = self.config.targets.get(chat_id)
        return target is not None and target.realtime_enabled

    def handle_history_message(self, message: dict[str, Any]) -> None:
        chat_id = int(message["chat_id"])
        target = self.config.targets.get(chat_id)
        if target is None or not target.history_enabled:
            return
        self._persist_message(message, MessageEvent.CREATED)

    @staticmethod
    def _text(content: dict[str, Any]) -> str | None:
        formatted = content.get("text")
        if isinstance(formatted, dict):
            value = formatted.get("text")
            return value if isinstance(value, str) else None
        caption = content.get("caption")
        if isinstance(caption, dict):
            value = caption.get("text")
            return value if isinstance(value, str) else None
        return None

    def _new_message(self, message: dict[str, Any]) -> None:
        chat_id = int(message["chat_id"])
        if not self._is_realtime_target(chat_id):
            return
        self._persist_message(message, MessageEvent.CREATED)

    def _persist_message(
        self,
        message: dict[str, Any],
        event: MessageEvent,
    ) -> None:
        chat_id = int(message["chat_id"])
        message_id = int(message["id"])
        revision = MessageRevision(
            account_id=self.account_id,
            chat_id=chat_id,
            message_id=message_id,
            revision_sequence=self.database.next_revision_sequence(
                account_id=self.account_id,
                chat_id=chat_id,
                message_id=message_id,
            ),
            observed_at=int(message.get("date", time.time())),
            text=self._text(message.get("content", {})),
            raw=message,
        )
        self.database.persist_message(revision, event)

    def _edit_message(self, update: dict[str, Any]) -> None:
        chat_id = int(update["chat_id"])
        if not self._is_realtime_target(chat_id):
            return
        message_id = int(update["message_id"])
        revision = MessageRevision(
            account_id=self.account_id,
            chat_id=chat_id,
            message_id=message_id,
            revision_sequence=self.database.next_revision_sequence(
                account_id=self.account_id,
                chat_id=chat_id,
                message_id=message_id,
            ),
            observed_at=int(update.get("edit_date", time.time())),
            text=self._text(update.get("new_content", {})),
            raw=update,
        )
        self.database.persist_message(revision, MessageEvent.EDITED)

    def _delete_messages(self, update: dict[str, Any]) -> None:
        chat_id = int(update["chat_id"])
        if not self._is_realtime_target(chat_id):
            return
        observed_at = int(time.time())
        for message_id in update.get("message_ids", []):
            self.database.mark_deleted(
                account_id=self.account_id,
                chat_id=chat_id,
                message_id=int(message_id),
                observed_at=observed_at,
            )

    def _chat(self, chat: dict[str, Any]) -> None:
        chat_type = chat.get("type", {}).get("@type", "unknown")
        usernames = chat.get("usernames", {}).get("active_usernames", [])
        self.database.upsert_chat(
            account_id=self.account_id,
            chat_id=int(chat["id"]),
            title=str(chat.get("title", "")),
            chat_type=str(chat_type),
            username=usernames[0] if usernames else None,
            raw=chat,
            observed_at=int(time.time()),
        )

    def _user(self, user: dict[str, Any]) -> None:
        usernames = user.get("usernames", {}).get("active_usernames", [])
        username = user.get("username") or (usernames[0] if usernames else None)
        self.database.upsert_user(
            account_id=self.account_id,
            user_id=int(user["id"]),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            username=username,
            phone_number=user.get("phone_number"),
            raw=user,
            observed_at=int(time.time()),
        )
