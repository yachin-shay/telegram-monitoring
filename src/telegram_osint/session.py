from __future__ import annotations

import os
import shutil
import tempfile
import hashlib
import json
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
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
        try:
            destination.relative_to(source)
        except ValueError:
            pass
        else:
            raise SessionConversionError("destination must not be inside tdata source")
        if destination.exists() and not force:
            raise SessionConversionError(
                f"destination exists: {destination}; use force to replace it"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with _conversion_lock(destination.parent):
            source_fingerprint = _tree_fingerprint(source)
            temporary_directory = Path(
                tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
            )
            temporary_session = temporary_directory / destination.name
            try:
                result = self._convert(source, temporary_session, passcode=passcode)
                if not temporary_session.exists():
                    raise SessionConversionError(
                        "conversion backend returned without creating a session"
                    )
                if _tree_fingerprint(source) != source_fingerprint:
                    raise SessionConversionError("tdata source changed during conversion")
                os.replace(temporary_session, destination)
                os.chmod(destination, 0o600)
                result = dict(result)
                result["session"] = str(destination)
                manifest = destination.with_suffix(destination.suffix + ".manifest.json")
                manifest.write_text(
                    json.dumps(
                        {
                            "source": str(source),
                            "source_fingerprint": source_fingerprint,
                            "session": str(destination),
                            "user_id": result.get("user_id"),
                            "username": result.get("username"),
                            "converted_at": datetime.now(timezone.utc).isoformat(),
                            "backend": type(self).__name__,
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                os.chmod(manifest, 0o600)
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


@contextmanager
def _conversion_lock(directory: Path):
    lock_path = directory / ".session-conversion.lock"
    directory.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SessionConversionError("another session conversion is running") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


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
