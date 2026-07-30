from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path
from typing import Any


def _timestamp(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0


def telethon_message_to_update(
    *,
    chat_id: int,
    message_id: int,
    text: str | None,
    date: datetime | None,
    raw: dict[str, Any],
) -> dict[str, Any]:
    return {
        "@type": "updateNewMessage",
        "message": {
            "id": message_id,
            "chat_id": str(chat_id),
            "date": _timestamp(date),
            "content": {
                "@type": "messageText",
                "text": {"text": text or "", "entities": []},
            },
            "_telethon_raw": raw,
        },
    }


class TelethonAdapter:
    """Small async boundary around Telethon and OpenTele2-compatible sessions."""

    def __init__(
        self,
        *,
        session_path: str | Path,
        api_id: int,
        api_hash: str,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.session_path = str(session_path)
        self.api_id = api_id
        self.api_hash = api_hash
        if client_factory is None:
            try:
                from telethon import TelegramClient
            except ImportError as error:
                raise RuntimeError("Telethon is required for collection") from error
            client_factory = TelegramClient
        self.client = client_factory(self.session_path, api_id, api_hash)

    async def connect(self) -> None:
        await self.client.connect()

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def get_me(self) -> Any:
        return await self.client.get_me()

    async def request(
        self,
        request: dict[str, Any],
        *,
        timeout: float = 60,
    ) -> dict[str, Any]:
        request_type = request.get("@type")
        if request_type == "getMe":
            return self._user_dict(await self.get_me())
        if request_type == "getUser":
            return self._user_dict(await self.client.get_entity(int(request["user_id"])))
        if request_type == "getUserFullInfo":
            from telethon.tl.functions.users import GetFullUserRequest

            result = await self.client(
                GetFullUserRequest(int(request["user_id"]))
            )
            return self._to_dict(result)
        if request_type == "getUserProfilePhotos":
            limit = int(request.get("limit", 100))
            offset = int(request.get("offset", 0))
            photos = [
                photo
                async for photo in self.client.iter_profile_photos(
                    int(request["user_id"]),
                    limit=limit,
                    offset=offset,
                )
            ]
            return {
                "@type": "chatPhotos",
                "total_count": offset + len(photos) + (1 if len(photos) == limit else 0),
                "photos": [self._to_dict(photo) for photo in photos],
            }
        if request_type == "getChatHistory":
            messages = [
                message
                async for message in self.iter_messages(
                    int(request["chat_id"]),
                    from_message_id=int(request.get("from_message_id", 0)),
                    limit=int(request.get("limit", 100)),
                )
            ]
            return {"@type": "messages", "messages": messages}
        raise ValueError(f"unsupported Telethon request: {request_type}")

    async def iter_messages(
        self,
        chat_id: int,
        *,
        from_message_id: int = 0,
        limit: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        kwargs: dict[str, Any] = {"limit": limit}
        if from_message_id:
            kwargs["offset_id"] = from_message_id
        async for message in self.client.iter_messages(chat_id, **kwargs):
            yield telethon_message_to_update(
                chat_id=chat_id,
                message_id=int(message.id),
                text=getattr(message, "message", None),
                date=getattr(message, "date", None),
                raw=self._to_dict(message),
            )["message"]

    async def dialogs(self) -> AsyncIterator[dict[str, Any]]:
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            yield {
                "id": str(dialog.id),
                "title": str(dialog.title or ""),
                "type": type(entity).__name__,
                "username": getattr(entity, "username", None),
            }

    def subscribe(self, update_handler: Callable[[dict[str, Any]], None]) -> None:
        try:
            from telethon import events
        except ImportError as error:
            raise RuntimeError("Telethon is required for event subscriptions") from error

        @self.client.on(events.NewMessage)
        async def new_message(event: Any) -> None:
            message = event.message
            update_handler(
                telethon_message_to_update(
                    chat_id=int(event.chat_id),
                    message_id=int(message.id),
                    text=getattr(message, "message", None),
                    date=getattr(message, "date", None),
                    raw=self._to_dict(message),
                )
            )

        @self.client.on(events.MessageEdited)
        async def edited_message(event: Any) -> None:
            message = event.message
            update_handler(
                {
                    "@type": "updateMessageContent",
                    "chat_id": str(event.chat_id),
                    "message_id": int(message.id),
                    "edit_date": _timestamp(getattr(message, "edit_date", None)),
                    "new_content": {
                        "@type": "messageText",
                        "text": {"text": getattr(message, "message", "") or ""},
                    },
                }
            )

        @self.client.on(events.MessageDeleted)
        async def deleted_message(event: Any) -> None:
            update_handler(
                {
                    "@type": "updateDeleteMessages",
                    "chat_id": str(event.chat_id),
                    "message_ids": [int(message_id) for message_id in event.deleted_ids],
                }
            )

    @staticmethod
    def _to_dict(value: Any) -> dict[str, Any]:
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if isinstance(value, dict):
            return value
        return {"value": repr(value)}

    @classmethod
    def _user_dict(cls, user: Any) -> dict[str, Any]:
        return {
            "@type": "user",
            "id": str(user.id),
            "first_name": getattr(user, "first_name", None),
            "last_name": getattr(user, "last_name", None),
            "username": getattr(user, "username", None),
            "phone_number": getattr(user, "phone", None),
            "_telethon_raw": cls._to_dict(user),
        }
