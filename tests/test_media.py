from pathlib import Path

from telegram_osint.media import MediaStore


def test_media_store_uses_content_hash_and_deduplicates(tmp_path: Path) -> None:
    source_one = tmp_path / "first.download"
    source_two = tmp_path / "second.download"
    source_one.write_bytes(b"same telegram content")
    source_two.write_bytes(b"same telegram content")
    store = MediaStore(tmp_path / "media")

    first = store.finalize(source_one)
    second = store.finalize(source_two)

    assert first.sha256 == second.sha256
    assert first.path == second.path
    assert first.path.read_bytes() == b"same telegram content"
    assert not source_one.exists()
    assert not source_two.exists()

