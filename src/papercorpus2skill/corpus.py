from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


SourceKind = Literal["pdf", "markdown"]


@dataclass(frozen=True)
class SourceFile:
    path: Path
    kind: SourceKind


MARKDOWN_SUFFIXES = {".md", ".markdown"}
PDF_SUFFIXES = {".pdf"}


def discover_sources(input_path: Path, include_zotero: bool = False) -> list[SourceFile]:
    """Discover supported paper files from a file or folder.

    Zotero support is local-first: if a Zotero storage/WebDAV-synced PDF exists
    on disk under the provided path, recursive discovery will include it.
    """
    path = Path(input_path).expanduser().resolve()
    candidates: list[Path]

    if path.is_file():
        candidates = [path]
    elif path.is_dir():
        search_root = _zotero_storage_root(path) if include_zotero else path
        candidates = [
            candidate for candidate in search_root.rglob("*")
            if candidate.is_file() and "markdown" not in (p.name for p in candidate.parents)
            and candidate.parent.name != "markdown"
        ]
    else:
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    sources = [_source_from_path(candidate) for candidate in sorted(candidates, key=lambda item: _sort_key(path, item))]
    return [source for source in sources if source is not None]


def _zotero_storage_root(path: Path) -> Path:
    storage = path / "storage"
    if storage.is_dir():
        return storage
    return path


def _source_from_path(path: Path) -> SourceFile | None:
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return SourceFile(path=path, kind="pdf")
    if suffix in MARKDOWN_SUFFIXES:
        return SourceFile(path=path, kind="markdown")
    return None


def _sort_key(root: Path, item: Path) -> tuple[int, str]:
    try:
        relative = item.relative_to(root)
    except ValueError:
        relative = item
    return (len(relative.parts), str(relative).lower())
