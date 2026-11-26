"""Where uploaded files live. Local folder for now (a Docker volume), behind a small interface
so cloud storage (S3, R2...) could be dropped in later.

File names are always generated here; the user's original file name is never used in a path.
"""
import re
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

_NAME = re.compile(r"^[0-9a-f]{32}\.(pdf|jpg|png)$")


class Storage(Protocol):
    def save(self, data: bytes, suffix: str) -> str: ...
    def path(self, stored_name: str) -> Path: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def save(self, data: bytes, suffix: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{suffix}"
        (self.root / name).write_bytes(data)
        return name

    def path(self, stored_name: str) -> Path:
        if not _NAME.match(stored_name):
            raise ValueError("Invalid stored file name")
        return self.root / stored_name


def get_storage() -> Storage:
    return LocalStorage(Path(get_settings().upload_dir))
