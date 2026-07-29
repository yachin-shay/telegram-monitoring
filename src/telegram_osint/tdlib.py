from __future__ import annotations

import asyncio
import ctypes
import json
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


class TdLibError(RuntimeError):
    pass


class NativeInterface(Protocol):
    def send(self, request: bytes) -> None: ...

    def receive(self, timeout: float) -> bytes | None: ...

    def execute(self, request: bytes) -> bytes: ...


class NativeTdJson:
    """ctypes binding to TDLib's current process-wide JSON interface."""

    def __init__(self, library_path: str | Path) -> None:
        try:
            self.library = ctypes.CDLL(str(library_path))
        except OSError as error:
            raise TdLibError(f"unable to load libtdjson: {error}") from error
        self.library.td_create_client_id.argtypes = []
        self.library.td_create_client_id.restype = ctypes.c_int
        self.library.td_send.argtypes = [ctypes.c_int, ctypes.c_char_p]
        self.library.td_send.restype = None
        self.library.td_receive.argtypes = [ctypes.c_double]
        self.library.td_receive.restype = ctypes.c_char_p
        self.library.td_execute.argtypes = [ctypes.c_char_p]
        self.library.td_execute.restype = ctypes.c_char_p
        self.client_id = int(self.library.td_create_client_id())

    def send(self, request: bytes) -> None:
        self.library.td_send(self.client_id, request)

    def receive(self, timeout: float) -> bytes | None:
        result = self.library.td_receive(timeout)
        return result if result else None

    def execute(self, request: bytes) -> bytes:
        result = self.library.td_execute(request)
        if not result:
            raise TdLibError("td_execute returned no result")
        return result


class TdJsonClient:
    def __init__(
        self,
        *,
        native: NativeInterface,
        update_handler: Callable[[dict[str, Any]], None],
    ) -> None:
        self.native = native
        self.update_handler = update_handler
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    async def start(self) -> None:
        if self._thread is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._thread = threading.Thread(
            target=self._receive_loop,
            name="tdlib-receiver",
            daemon=True,
        )
        self._thread.start()

    def send(self, request: dict[str, Any]) -> None:
        self.native.send(json.dumps(request, separators=(",", ":")).encode())

    async def request(
        self,
        request: dict[str, Any],
        *,
        timeout: float = 60,
    ) -> dict[str, Any]:
        if self._loop is None:
            raise TdLibError("TDLib client has not been started")
        correlation = uuid.uuid4().hex
        envelope = dict(request)
        envelope["@extra"] = correlation
        future = self._loop.create_future()
        self._pending[correlation] = future
        self.send(envelope)
        try:
            response = await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(correlation, None)
        if response.get("@type") == "error":
            raise TdLibError(
                f"Telegram error {response.get('code')}: {response.get('message')}"
            )
        return response

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.native.execute(
            json.dumps(request, separators=(",", ":")).encode()
        )
        return json.loads(result)

    def _receive_loop(self) -> None:
        while not self._stop.is_set():
            raw = self.native.receive(0.1)
            if raw is None:
                continue
            try:
                item = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._dispatch, item)

    def _dispatch(self, item: dict[str, Any]) -> None:
        correlation = item.get("@extra")
        if correlation is not None and correlation in self._pending:
            future = self._pending[correlation]
            if not future.done():
                future.set_result(item)
            return
        self.update_handler(item)

    async def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            await asyncio.to_thread(self._thread.join, 1)
            self._thread = None
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()


class Authorization:
    """Explicit TDLib authorization state translator."""

    def __init__(
        self,
        *,
        send: Callable[[dict[str, Any]], None],
        api_id: int,
        api_hash: str,
        database_directory: str,
        files_directory: str,
    ) -> None:
        self.send = send
        self.api_id = api_id
        self.api_hash = api_hash
        self.database_directory = database_directory
        self.files_directory = files_directory
        self.state = "unknown"
        self.qr_link: str | None = None

    def handle(self, state: dict[str, Any]) -> None:
        self.state = str(state.get("@type", "unknown"))
        if self.state == "authorizationStateWaitTdlibParameters":
            self.send(
                {
                    "@type": "setTdlibParameters",
                    "use_test_dc": False,
                    "database_directory": self.database_directory,
                    "files_directory": self.files_directory,
                    "database_encryption_key": "",
                    "use_file_database": True,
                    "use_chat_info_database": True,
                    "use_message_database": True,
                    "use_secret_chats": False,
                    "api_id": self.api_id,
                    "api_hash": self.api_hash,
                    "system_language_code": "en",
                    "device_model": "telegram-osint",
                    "application_version": "0.1.0",
                }
            )
        elif self.state == "authorizationStateWaitPhoneNumber":
            self.send({"@type": "requestQrCodeAuthentication", "other_user_ids": []})
        elif self.state == "authorizationStateWaitOtherDeviceConfirmation":
            self.qr_link = state.get("link")

    def submit_phone(self, phone_number: str) -> None:
        self.send(
            {
                "@type": "setAuthenticationPhoneNumber",
                "phone_number": phone_number,
            }
        )

    def submit_code(self, code: str) -> None:
        self.send({"@type": "checkAuthenticationCode", "code": code})

    def submit_password(self, password: str) -> None:
        self.send({"@type": "checkAuthenticationPassword", "password": password})

