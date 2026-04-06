from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def save(self, name: str, data: bytes) -> None:
        ...

    def delete(self, name: str) -> None:
        ...


class LocalStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: bytes) -> None:
        path = self.base_dir / name
        path.write_bytes(data)

    def delete(self, name: str) -> None:
        path = self.base_dir / name
        if path.exists() and path.is_file():
            path.unlink()
