"""Keep unique upload writes aligned with the request's database transaction."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)
INFO_KEY = "vericlue_file_changes"


class FileChanges:
    def __init__(self, media_dir: str) -> None:
        self.root = Path(media_dir).resolve()
        self.created: set[Path] = set()
        self.superseded: set[Path] = set()

    def track(self, path: Path) -> None:
        self._validate(path)
        self.created.add(path)

    def replace(self, paths: list[Path | None]) -> None:
        for path in paths:
            if path is not None:
                self._validate(path)
                self.superseded.add(path)

    def _validate(self, path: Path) -> None:
        if (
            path.is_symlink()
            or path.parent.is_symlink()
            or path.parent.is_junction()
            or not path.resolve().is_relative_to(self.root)
            or path.resolve() == self.root
        ):
            raise ValueError("Unsafe upload cleanup path")

    def _delete(self, paths: set[Path]) -> None:
        for path in paths:
            try:
                self._validate(path)
                path.unlink(missing_ok=True)
            except (OSError, ValueError):
                # A post-commit cleanup failure must not turn a committed success
                # into an HTTP error. Session TTL cleanup remains the fallback.
                logger.error("upload_cleanup_deferred")

    def commit(self) -> None:
        self._delete(self.superseded - self.created)

    def rollback(self) -> None:
        self._delete(self.created)


def file_changes(db: DBSession, media_dir: str) -> FileChanges:
    """Return request-scoped file tracking, never a global/shared mutable registry."""
    if INFO_KEY not in db.info:
        db.info[INFO_KEY] = FileChanges(media_dir)
    return db.info[INFO_KEY]
