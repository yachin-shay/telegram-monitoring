from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigError(ValueError):
    pass


def _strict_keys(data: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{context} has unknown keys: {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class AccountConfig:
    name: str
    api_id: int
    api_hash: str


@dataclass(frozen=True, slots=True)
class PathConfig:
    tdlib: Path
    database: Path
    media: Path
    socket: Path


@dataclass(frozen=True, slots=True)
class MediaPolicy:
    enabled: bool = False
    types: tuple[str, ...] = ("photo", "video", "document", "audio", "voice")
    max_bytes: int = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PhotoPolicy:
    mode: str = "off"
    download: bool = False
    max_bytes: int = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ProfilePolicy:
    enabled: bool = True
    snapshot_on_change: bool = True
    photos: PhotoPolicy = field(default_factory=PhotoPolicy)


@dataclass(frozen=True, slots=True)
class TargetConfig:
    chat_id: int
    history_enabled: bool = True
    realtime_enabled: bool = True
    media: MediaPolicy = field(default_factory=MediaPolicy)
    profiles: ProfilePolicy = field(default_factory=ProfilePolicy)


@dataclass(frozen=True, slots=True)
class AppConfig:
    source: Path
    schema_version: int
    account: AccountConfig
    paths: PathConfig
    targets: dict[int, TargetConfig]
    plugins: dict[str, dict[str, Any]]
    config_hash: str


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a mapping")
    return value


def _enabled(value: Any, context: str, default: bool = True) -> bool:
    data = _mapping(value, context)
    _strict_keys(data, {"enabled"}, context)
    enabled = data.get("enabled", default)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{context}.enabled must be boolean")
    return enabled


def _parse_media(value: Any) -> MediaPolicy:
    data = _mapping(value, "target.media")
    _strict_keys(data, {"enabled", "types", "max_bytes"}, "target.media")
    types = data.get("types", ["photo", "video", "document", "audio", "voice"])
    if not isinstance(types, list) or not all(isinstance(item, str) for item in types):
        raise ConfigError("target.media.types must be a list of strings")
    max_bytes = data.get("max_bytes", 100 * 1024 * 1024)
    if not isinstance(max_bytes, int) or max_bytes < 0:
        raise ConfigError("target.media.max_bytes must be a non-negative integer")
    enabled = data.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("target.media.enabled must be boolean")
    return MediaPolicy(enabled=enabled, types=tuple(types), max_bytes=max_bytes)


def _parse_profiles(value: Any) -> ProfilePolicy:
    data = _mapping(value, "target.profiles")
    _strict_keys(data, {"enabled", "snapshot_on_change", "photos"}, "target.profiles")
    photos_data = _mapping(data.get("photos"), "target.profiles.photos")
    _strict_keys(
        photos_data,
        {"mode", "download", "max_bytes"},
        "target.profiles.photos",
    )
    mode = photos_data.get("mode", "off")
    if mode not in {"off", "current", "all_visible_history"}:
        raise ConfigError("profile photo mode must be off, current, or all_visible_history")
    max_bytes = photos_data.get("max_bytes", 20 * 1024 * 1024)
    if not isinstance(max_bytes, int) or max_bytes < 0:
        raise ConfigError("profile photo max_bytes must be non-negative")
    return ProfilePolicy(
        enabled=bool(data.get("enabled", True)),
        snapshot_on_change=bool(data.get("snapshot_on_change", True)),
        photos=PhotoPolicy(
            mode=mode,
            download=bool(photos_data.get("download", False)),
            max_bytes=max_bytes,
        ),
    )


def _canonical_hash(data: Mapping[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_config(
    path: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    source = Path(path).resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"cannot read configuration: {error}") from error
    data = _mapping(raw, "configuration")
    _strict_keys(
        data,
        {"schema_version", "account", "paths", "targets", "plugins"},
        "configuration",
    )
    if data.get("schema_version") != 1:
        raise ConfigError("schema_version must be 1")

    account_data = _mapping(data.get("account"), "account")
    _strict_keys(account_data, {"name", "api_id", "api_hash", "api_hash_env"}, "account")
    environment = os.environ if environ is None else environ
    if "api_hash_env" in account_data:
        variable = str(account_data["api_hash_env"])
        api_hash = environment.get(variable, "")
        if not api_hash:
            raise ConfigError(f"environment variable {variable} is not set")
    else:
        api_hash = str(account_data.get("api_hash", ""))
    if not api_hash:
        raise ConfigError("account api_hash or api_hash_env is required")
    try:
        account = AccountConfig(
            name=str(account_data["name"]),
            api_id=int(account_data["api_id"]),
            api_hash=api_hash,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError("account.name and integer account.api_id are required") from error

    path_data = _mapping(data.get("paths"), "paths")
    _strict_keys(path_data, {"tdlib", "database", "media", "socket"}, "paths")
    base = source.parent

    def resolve(name: str, default: str | None = None) -> Path:
        value = path_data.get(name, default)
        if value is None:
            raise ConfigError(f"paths.{name} is required")
        candidate = Path(str(value))
        return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()

    paths = PathConfig(
        tdlib=resolve("tdlib"),
        database=resolve("database"),
        media=resolve("media"),
        socket=resolve("socket", "state/daemon.sock"),
    )
    if len({paths.tdlib, paths.database, paths.media, paths.socket}) != 4:
        raise ConfigError("configured paths must be distinct")

    targets_data = _mapping(data.get("targets"), "targets")
    targets: dict[int, TargetConfig] = {}
    for raw_chat_id, raw_target in targets_data.items():
        try:
            chat_id = int(raw_chat_id)
        except (TypeError, ValueError) as error:
            raise ConfigError(f"invalid target chat ID: {raw_chat_id}") from error
        target_data = _mapping(raw_target, f"target {chat_id}")
        _strict_keys(
            target_data,
            {"history", "realtime", "media", "profiles", "members"},
            f"target {chat_id}",
        )
        targets[chat_id] = TargetConfig(
            chat_id=chat_id,
            history_enabled=_enabled(target_data.get("history"), "target.history"),
            realtime_enabled=_enabled(target_data.get("realtime"), "target.realtime"),
            media=_parse_media(target_data.get("media")),
            profiles=_parse_profiles(target_data.get("profiles")),
        )

    plugins = _mapping(data.get("plugins"), "plugins")
    return AppConfig(
        source=source,
        schema_version=1,
        account=account,
        paths=paths,
        targets=targets,
        plugins=plugins,
        config_hash=_canonical_hash(data),
    )


def mutate_config(
    path: str | Path,
    *,
    expected_hash: str,
    operation: str,
    arguments: Mapping[str, Any],
) -> AppConfig:
    source = Path(path).resolve()
    current = load_config(source)
    if current.config_hash != expected_hash:
        raise ConfigError("configuration changed; reload and retry")
    data = _mapping(yaml.safe_load(source.read_text(encoding="utf-8")), "configuration")
    targets = data.setdefault("targets", {})
    chat_id = str(int(arguments["chat_id"]))
    if operation == "target_add":
        targets.setdefault(
            chat_id,
            {
                "history": {"enabled": True},
                "realtime": {"enabled": True},
                "media": {"enabled": False},
            },
        )
    elif operation == "target_remove":
        targets.pop(chat_id, None)
    elif operation == "target_media":
        target = targets.setdefault(chat_id, {})
        media = target.setdefault("media", {})
        media["enabled"] = bool(arguments["enabled"])
    else:
        raise ConfigError(f"unsupported configuration operation: {operation}")

    rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    source.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{source.name}.",
        dir=source.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
        replacement = Path(temporary_name)
        load_config(replacement)
        os.replace(replacement, source)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
    return load_config(source)

