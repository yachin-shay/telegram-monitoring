from __future__ import annotations

import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SessionConversionError(RuntimeError):
    """Raised when a Desktop session cannot be safely converted."""


class SessionConverter(ABC):
    """Safe, destination-isolated boundary for tdata conversion backends."""

    def convert(
        self,
        tdata_path: str | Path,
        session_path: str | Path,
        *,
        passcode: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        source_input = Path(tdata_path).expanduser()
        if source_input.is_symlink():
            raise SessionConversionError("tdata source must not be a symlink")
        source = source_input.resolve()
        destination = Path(session_path).expanduser().resolve()
        if not source.is_dir():
            raise SessionConversionError(f"tdata directory does not exist: {source}")
        if destination.exists() and not force:
            raise SessionConversionError(
                f"destination exists: {destination}; use force to replace it"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
        )
        temporary_session = temporary_directory / destination.name
        try:
            result = self._convert(
                source,
                temporary_session,
                passcode=passcode,
            )
            if not temporary_session.exists():
                raise SessionConversionError(
                    "conversion backend returned without creating a session"
                )
            if force and destination.exists():
                destination.unlink()
            os.replace(temporary_session, destination)
            os.chmod(destination, 0o600)
            result = dict(result)
            result["session"] = str(destination)
            return result
        except SessionConversionError:
            raise
        except Exception as error:
            raise SessionConversionError(str(error)) from error
        finally:
            shutil.rmtree(temporary_directory, ignore_errors=True)

    @abstractmethod
    def _convert(
        self,
        tdata_path: Path,
        session_path: Path,
        *,
        passcode: str | None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class OpenTele2Converter(SessionConverter):
    """OpenTele2 implementation; imports lazily so core commands stay usable."""

    def _convert(
        self,
        tdata_path: Path,
        session_path: Path,
        *,
        passcode: str | None,
    ) -> dict[str, Any]:
        try:
            from opentele2.api import API, UseCurrentSession
            from opentele2.td import TDesktop
        except ImportError as error:
            raise SessionConversionError(
                "OpenTele2 is required for tdata conversion"
            ) from error

        try:
            desktop = TDesktop(str(tdata_path), passcode=passcode)
        except Exception as error:
            raise SessionConversionError(f"OpenTele2 could not load tdata: {error}") from error
        if not desktop.isLoaded():
            raise SessionConversionError("OpenTele2 could not load tdata")
        api = API.TelegramDesktop.Generate()
        client = _run_async(
            desktop.ToTelethon(
                str(session_path),
                UseCurrentSession,
                api,
            )
        )
        user = _run_async(_validate_client(client))
        return {"user_id": int(user.id), "username": getattr(user, "username", None)}


async def _validate_client(client: Any) -> Any:
    try:
        await client.connect()
        user = await client.get_me()
        return user
    finally:
        await client.disconnect()


def _run_async(awaitable: Any) -> Any:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise SessionConversionError(
        "tdata conversion must run outside an active event loop"
    )
