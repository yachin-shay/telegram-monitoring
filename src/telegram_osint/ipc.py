from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import uuid
from pathlib import Path
from typing import Any

from telegram_osint.config import AppConfig
from telegram_osint.storage import Database


MAX_FRAME_BYTES = 1024 * 1024


class ControlServer:
    def __init__(
        self,
        *,
        config: AppConfig,
        database: Database,
        account_id: int,
        extra_handler: Any | None = None,
    ) -> None:
        self.config = config
        self.database = database
        self.account_id = account_id
        self.extra_handler = extra_handler
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.config.paths.socket.parent.mkdir(parents=True, exist_ok=True)
        self.config.paths.socket.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.config.paths.socket,
            limit=MAX_FRAME_BYTES,
        )
        os.chmod(self.config.paths.socket, 0o600)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self.config.paths.socket.unlink(missing_ok=True)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            peer_socket = writer.get_extra_info("socket")
            if peer_socket is not None and hasattr(socket, "SO_PEERCRED"):
                credentials = peer_socket.getsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_PEERCRED,
                    struct.calcsize("3i"),
                )
                _pid, uid, _gid = struct.unpack("3i", credentials)
                if uid != os.getuid():
                    writer.write(b'{"ok":false,"error":"unauthorized local peer"}\n')
                    await writer.drain()
                    return
            line = await reader.readline()
            if len(line) > MAX_FRAME_BYTES:
                response = {"ok": False, "error": "request frame is too large"}
            else:
                try:
                    request = json.loads(line)
                    response = self._dispatch(
                        str(request.get("command", "")),
                        request.get("arguments", {}),
                    )
                except (ValueError, TypeError, KeyError) as error:
                    response = {"ok": False, "error": str(error)}
            writer.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def _dispatch(self, command: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if command == "status":
            result: Any = {
                "account": self.config.account.name,
                "account_id": self.account_id,
                "config_hash": self.config.config_hash,
                "targets": len(self.config.targets),
            }
        elif command == "chats.list":
            result = self.database.list_chats(self.account_id)
        elif command == "users.scrape":
            user_id = int(arguments["user_id"])
            photos = str(arguments.get("photos", "current"))
            if photos not in {"off", "current", "all_visible_history"}:
                raise ValueError("invalid photo mode")
            job_id = self.database.enqueue_job(
                kind="user_scrape",
                payload={"user_id": user_id, "photos": photos},
                deduplication_key=f"user:{user_id}:{photos}",
            )
            result = {"job_id": job_id}
        elif command == "jobs.show":
            job = self.database.get_job(str(arguments["job_id"]))
            result = {
                "id": job.id,
                "kind": job.kind,
                "state": job.state,
                "payload": job.payload,
                "attempts": job.attempts,
            }
        elif self.extra_handler is not None:
            result = self.extra_handler(command, arguments)
        else:
            return {"ok": False, "error": f"unknown command: {command}"}
        return {"ok": True, "result": result}


class ControlClient:
    def __init__(self, socket_path: str | Path) -> None:
        self.socket_path = Path(socket_path)

    async def request(
        self,
        command: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        request = {
            "version": 1,
            "request_id": uuid.uuid4().hex,
            "command": command,
            "arguments": arguments,
        }
        writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
        await writer.drain()
        line = await reader.readline()
        writer.close()
        await writer.wait_closed()
        if not line:
            raise ConnectionError("daemon closed without a response")
        return json.loads(line)
