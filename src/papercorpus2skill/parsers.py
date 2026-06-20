from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from papercorpus2skill.corpus import SourceFile


@dataclass(frozen=True)
class ParsedDocument:
    source: SourceFile
    title: str
    text: str


class PDFParserDependencyError(RuntimeError):
    pass


def parse_source(source: SourceFile) -> ParsedDocument:
    if source.kind == "markdown":
        return _parse_markdown(source)
    if source.kind == "pdf":
        return _parse_pdf(source)
    raise ValueError(f"Unsupported source kind: {source.kind}")


def parse_many(sources: list[SourceFile]) -> list[ParsedDocument]:
    return [parse_source(source) for source in sources]


def _parse_markdown(source: SourceFile) -> ParsedDocument:
    text = source.path.read_text(encoding="utf-8")
    return ParsedDocument(source=source, title=_title_from_markdown(source.path, text), text=text.strip())


def _parse_pdf(source: SourceFile) -> ParsedDocument:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PDFParserDependencyError(
            "PDF parsing requires PyMuPDF. Install with `uv pip install 'papercorpus2skill[pdf]'` "
            "or `uv add PyMuPDF`."
        ) from exc

    parts: list[str] = []
    with fitz.open(source.path) as doc:
        for page in doc:
            page_text = page.get_text("text").strip()
            if page_text:
                parts.append(page_text)
    return ParsedDocument(source=source, title=source.path.stem, text="\n\n".join(parts).strip())


def _title_from_markdown(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or path.stem
    return path.stem
