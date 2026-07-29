from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoredMedia:
    path: Path
    sha256: str
    size: int


class MediaStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def finalize(self, source: str | Path) -> StoredMedia:
        candidate = Path(source).resolve()
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError("download source must be a regular file")
        digest = hashlib.sha256()
        size = 0
        with candidate.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        sha256 = digest.hexdigest()
        destination = self.root / sha256[:2] / sha256[2:4] / sha256
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            candidate.unlink()
        else:
            os.replace(candidate, destination)
        return StoredMedia(path=destination, sha256=sha256, size=size)

