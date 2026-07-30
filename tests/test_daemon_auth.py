import asyncio
from pathlib import Path

import pytest

from telegram_osint.config import load_config
from telegram_osint.daemon import Daemon


class UnauthorizedClient:
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    def subscribe(self, callback) -> None:
        pass

    async def get_me(self):
        return None


def test_daemon_reports_unauthorized_session_instead_of_attribute_error(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "account.yaml"
    config_path.write_text(
        """
schema_version: 1
account: {name: test, api_id: 1, api_hash: value}
paths:
  tdata: tdata
  session: account.session
  database: data.sqlite3
  media: media
  socket: daemon.sock
targets: {}
""",
        encoding="utf-8",
    )
    (tmp_path / "account.session").touch()
    daemon = Daemon(load_config(config_path))
    daemon.client = UnauthorizedClient()

    with pytest.raises(RuntimeError, match="not authenticated"):
        asyncio.run(daemon.run())
