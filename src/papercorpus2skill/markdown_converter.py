from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from papercorpus2skill.corpus import SourceFile
from papercorpus2skill.parsers import PDFParserDependencyError


@dataclass(frozen=True)
class MarkdownDocument:
    source: SourceFile
    title: str
    markdown_path: Path
    markdown: str


class MarkdownCacheConverter:
    def __init__(self, cache_dir: Path, pdf_backend: str = "pymupdf") -> None:
        self.cache_dir = Path(cache_dir)
        self.pdf_backend = pdf_backend

    def convert_many(self, sources: list[SourceFile]) -> list[MarkdownDocument]:
        return [self.convert(source) for source in sources]

    def convert(self, source: SourceFile) -> MarkdownDocument:
        if source.kind == "pdf":
            _validate_pdf_backend(self.pdf_backend)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.cache_dir / f"{_stable_id(source.path)}.md"
        if markdown_path.exists():
            markdown = markdown_path.read_text(encoding="utf-8")
            return MarkdownDocument(source=source, title=_title_from_markdown(source.path, markdown), markdown_path=markdown_path, markdown=markdown)

        if source.kind == "markdown":
            markdown = source.path.read_text(encoding="utf-8").strip()
        elif source.kind == "pdf":
            markdown = _pdf_to_markdown(source.path, self.pdf_backend)
        else:
            raise ValueError(f"Unsupported source kind: {source.kind}")

        markdown = _normalize_markdown(markdown)
        markdown_path.write_text(markdown + "\n", encoding="utf-8")
        return MarkdownDocument(source=source, title=_title_from_markdown(source.path, markdown), markdown_path=markdown_path, markdown=markdown)


class PDFBackendError(RuntimeError):
    pass


def _validate_pdf_backend(backend: str) -> None:
    if backend not in {"pymupdf", "pymupdf4llm", "docling"}:
        raise PDFBackendError(f"Unsupported PDF backend: {backend}. Use pymupdf, pymupdf4llm, or docling.")


def _pdf_to_markdown(path: Path, backend: str) -> str:
    if backend == "pymupdf4llm":
        return _pdf_to_markdown_pymupdf4llm(path)
    if backend == "docling":
        return _pdf_to_markdown_docling(path)
    return _pdf_to_markdown_pymupdf(path)


def _pdf_to_markdown_pymupdf(path: Path) -> str:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PDFParserDependencyError(
            "PDF to Markdown conversion requires PyMuPDF. Install with `uv sync --extra pdf` or `uv add PyMuPDF`."
        ) from exc

    pages: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            blocks = page.get_text("blocks")
            blocks = sorted(blocks, key=lambda block: (round(block[1], 1), round(block[0], 1)))
            lines: list[str] = []
            for block in blocks:
                text = str(block[4]).strip()
                if text:
                    lines.append(text)
            page_text = "\n\n".join(lines).strip()
            if page_text:
                pages.append(page_text)
    return "\n\n".join(pages)


def _pdf_to_markdown_pymupdf4llm(path: Path) -> str:
    try:
        import pymupdf4llm  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PDFBackendError("PDF backend `pymupdf4llm` is not installed. Install it or set processing.pdf_backend: pymupdf.") from exc
    return str(pymupdf4llm.to_markdown(str(path))).strip()


def _pdf_to_markdown_docling(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PDFBackendError("PDF backend `docling` is not installed. Install it or set processing.pdf_backend: pymupdf.") from exc
    result = DocumentConverter().convert(str(path))
    return result.document.export_to_markdown().strip()


def _normalize_markdown(markdown: str) -> str:
    lines = []
    for raw_line in markdown.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if _looks_like_page_number(line):
            continue
        lines.append(_promote_heading(line))
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _promote_heading(line: str) -> str:
    if line.startswith("#"):
        return line
    heading = line.strip(" :.-")
    lowered = heading.lower()
    common = {
        "abstract",
        "摘要",
        "introduction",
        "引言",
        "绪论",
        "related work",
        "相关工作",
        "literature review",
        "文献综述",
        "method",
        "methods",
        "methodology",
        "方法",
        "experiments",
        "results",
        "实验",
        "结果",
        "discussion",
        "讨论",
        "conclusion",
        "结论",
        "references",
        "参考文献",
        "bibliography",
    }
    if lowered in common or heading in common:
        return f"## {heading}"
    return line


def _looks_like_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"[-—]?\s*\d{1,4}\s*[-—]?", line))


def _title_from_markdown(path: Path, markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or path.stem
    return path.stem


def _stable_id(path: Path) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]
