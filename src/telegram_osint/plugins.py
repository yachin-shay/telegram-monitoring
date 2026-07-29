from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from telegram_osint.storage import Database


Plugin = Callable[[dict[str, Any]], None]


class OutboxDispatcher:
    """At-least-once plugin delivery with a durable per-plugin cursor."""

    def __init__(
        self,
        *,
        database: Database,
        plugins: Mapping[str, Plugin],
    ) -> None:
        self.database = database
        self.plugins = plugins

    def dispatch(self) -> int:
        delivered = 0
        for plugin_name, plugin in self.plugins.items():
            for event in self.database.pending_outbox(plugin_name):
                plugin(event)
                self.database.mark_outbox_delivered(plugin_name, event["id"])
                delivered += 1
        return delivered

