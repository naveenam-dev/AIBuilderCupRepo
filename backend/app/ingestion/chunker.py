"""Heading-aware chunking: split on Markdown headings first, then pack paragraphs up to a size budget."""
import re

from app.models import Chunk, Document

_HEADING = re.compile(r"^#{1,6}\s", re.MULTILINE)


def _sections(text: str) -> list[str]:
    starts = [m.start() for m in _HEADING.finditer(text)]
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    bounds = [*starts, len(text)]
    return [text[a:b].strip() for a, b in zip(bounds, bounds[1:]) if text[a:b].strip()]


def _pack(section: str, size: int, overlap: int) -> list[str]:
    if len(section) <= size:
        return [section]
    pieces, current = [], ""
    for para in re.split(r"\n\s*\n|\n(?=[-*\d])", section):
        if current and len(current) + len(para) + 1 > size:
            pieces.append(current.strip())
            current = current[-overlap:] if overlap else ""
        current += "\n" + para
    if current.strip():
        pieces.append(current.strip())
    return pieces


def chunk_document(doc: Document, size: int = 1200, overlap: int = 150) -> list[Chunk]:
    texts = [p for s in _sections(doc.content) for p in _pack(s, size, overlap)]
    return [
        Chunk(
            id=f"{doc.id}#{i}",
            doc_id=doc.id,
            ordinal=i,
            # Prefix the title so each chunk carries its context into both embedding and keyword index.
            text=f"{doc.title}\n\n{t}",
            source=doc.source,
            title=doc.title,
            url=doc.url,
            acl_roles=doc.acl_roles,
            updated_at=doc.updated_at,
        )
        for i, t in enumerate(texts)
    ]
