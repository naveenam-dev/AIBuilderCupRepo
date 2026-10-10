"""Reads exported/mock artifacts from seed_data/<source>/*.md.

File format: a front-matter block of `key: value` lines between `---` markers, then a Markdown body.
Recognized keys: id, title, url, author, updated_at, acl (comma-separated roles). Others go to metadata.
"""
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from app.connectors.base import SourceConnector
from app.models import Document, SourceType

_CORE_KEYS = {"id", "title", "url", "author", "updated_at", "acl"}


def parse_seed_file(path: Path, source: SourceType) -> Document:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---"):
        _, header, body = raw.split("---", 2)
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return Document(
        id=meta.get("id", path.stem),
        source=source,
        title=meta.get("title", path.stem),
        content=body.strip(),
        url=meta.get("url", ""),
        author=meta.get("author", ""),
        updated_at=datetime.fromisoformat(meta["updated_at"]) if meta.get("updated_at") else None,
        acl_roles=[r.strip() for r in meta.get("acl", "all").split(",") if r.strip()],
        metadata={k: v for k, v in meta.items() if k not in _CORE_KEYS},
    )


class SeedFileConnector(SourceConnector):
    def __init__(self, root: Path, source: SourceType):
        self.root = root / source
        self.source = source

    def list_documents(self) -> Iterator[Document]:
        for path in sorted(self.root.glob("*.md")):
            yield parse_seed_file(path, self.source)


def seed_connectors(seed_dir: Path) -> list[SourceConnector]:
    return [SeedFileConnector(seed_dir, s) for s in ("confluence", "slack", "jira", "email") if (seed_dir / s).is_dir()]
