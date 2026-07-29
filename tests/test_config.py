from pathlib import Path

import pytest

from telegram_osint.config import ConfigError, load_config, mutate_config


def test_config_resolves_paths_and_target_policy(tmp_path: Path) -> None:
    path = tmp_path / "account.yaml"
    path.write_text(
        """
schema_version: 1
account:
  name: research
  api_id: 12345
  api_hash_env: TG_API_HASH
paths:
  tdlib: state/tdlib
  database: state/data.sqlite3
  media: state/media
targets:
  "-10042":
    history: {enabled: true}
    realtime: {enabled: true}
    media: {enabled: false, max_bytes: 1024}
""",
        encoding="utf-8",
    )

    config = load_config(path, environ={"TG_API_HASH": "secret"})

    assert config.account.name == "research"
    assert config.paths.database == tmp_path / "state/data.sqlite3"
    assert config.targets[-10042].media.enabled is False
    assert config.targets[-10042].media.max_bytes == 1024
    assert len(config.config_hash) == 64


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths: {tdlib: td, database: db.sqlite3, media: media}
unexpected: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unknown keys.*unexpected"):
        load_config(path)


def test_explicit_mutation_updates_yaml_with_conflict_protection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "account.yaml"
    path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths: {tdlib: td, database: db.sqlite3, media: media}
targets: {}
""",
        encoding="utf-8",
    )
    original = load_config(path)

    updated = mutate_config(
        path,
        expected_hash=original.config_hash,
        operation="target_add",
        arguments={"chat_id": -10099},
    )

    assert -10099 in updated.targets
    with pytest.raises(ConfigError, match="configuration changed"):
        mutate_config(
            path,
            expected_hash=original.config_hash,
            operation="target_remove",
            arguments={"chat_id": -10099},
        )

