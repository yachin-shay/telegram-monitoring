from pathlib import Path

import pytest

from telegram_osint.session import SessionConversionError, SessionConverter


class FakeConverter(SessionConverter):
    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path, str | None]] = []

    def _convert(
        self,
        tdata_path: Path,
        session_path: Path,
        *,
        passcode: str | None = None,
        force: bool = False,
    ) -> dict[str, object]:
        self.calls.append((tdata_path, session_path, passcode))
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_bytes(b"telethon-session")
        return {"user_id": 42, "session": str(session_path)}


def test_conversion_requires_tdata_directory_and_writes_new_session(
    tmp_path: Path,
) -> None:
    tdata = tmp_path / "tdata"
    tdata.mkdir()
    output = tmp_path / "state" / "account.session"
    converter = FakeConverter()

    result = converter.convert(tdata, output, passcode="secret")

    assert result["user_id"] == 42
    assert output.read_bytes() == b"telethon-session"
    assert converter.calls[0][0] == tdata
    assert converter.calls[0][2] == "secret"


def test_conversion_refuses_missing_tdata(tmp_path: Path) -> None:
    converter = FakeConverter()

    with pytest.raises(SessionConversionError, match="tdata directory"):
        converter.convert(
            tmp_path / "missing",
            tmp_path / "account.session",
        )


def test_conversion_refuses_existing_output_without_force(tmp_path: Path) -> None:
    tdata = tmp_path / "tdata"
    tdata.mkdir()
    output = tmp_path / "account.session"
    output.write_bytes(b"old")
    converter = FakeConverter()

    with pytest.raises(SessionConversionError, match="destination exists"):
        converter.convert(tdata, output)


def test_force_conversion_replaces_atomically_and_writes_manifest(tmp_path: Path) -> None:
    tdata = tmp_path / "tdata"
    tdata.mkdir()
    (tdata / "key").write_bytes(b"stable")
    output = tmp_path / "account.session"
    output.write_bytes(b"old")

    result = FakeConverter().convert(tdata, output, force=True)

    assert result["session"] == str(output.resolve())
    assert output.read_bytes() == b"telethon-session"
    assert output.with_suffix(".session.manifest.json").is_file()
    assert (tdata / "key").read_bytes() == b"stable"


def test_conversion_rejects_destination_inside_source(tmp_path: Path) -> None:
    tdata = tmp_path / "tdata"
    tdata.mkdir()
    with pytest.raises(SessionConversionError, match="inside"):
        FakeConverter().convert(tdata, tdata / "account.session")
