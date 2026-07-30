from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MessageEvent(StrEnum):
    CREATED = "created"
    EDITED = "edited"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class MessageRevision:
    account_id: int
    chat_id: int
    message_id: int
    revision_sequence: int
    observed_at: int
    text: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    kind: str
    state: str
    payload: dict[str, Any]
    attempts: int
    progress: dict[str, Any]
