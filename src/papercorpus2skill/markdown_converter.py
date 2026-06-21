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
        total = len(sources)
        results: list[MarkdownDocument] = []
        for index, source in enumerate(sources):
            doc = self.convert(source, index=index, total=total)
            results.append(doc)
        return results

    def convert(self, source: SourceFile, index: int | None = None, total: int | None = None) -> MarkdownDocument:
        if source.kind == "pdf":
            _validate_pdf_backend(self.pdf_backend)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.cache_dir / f"{_stable_id(source.path)}.md"

        prefix = f"  [{index + 1}/{total}]" if index is not None and total is not None else ""

        if markdown_path.exists():
            print(f"{prefix} (cached) {source.path.name}")
            markdown = markdown_path.read_text(encoding="utf-8")
            return MarkdownDocument(source=source, title=_title_from_markdown(source.path, markdown), markdown_path=markdown_path, markdown=markdown)

        if source.kind == "markdown":
            print(f"{prefix} {source.path.name}")
            markdown = source.path.read_text(encoding="utf-8").strip()
        elif source.kind == "pdf":
            print(f"{prefix} Converting {source.path.name}...", end="", flush=True)
            markdown = _pdf_to_markdown(source.path, self.pdf_backend)
            print(" done.")
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
        total = len(doc)
        for page_index, page in enumerate(doc):
            if total > 10 and page_index % 5 == 0:
                print(f"\r  page {page_index + 1}/{total}...", end="", flush=True)

            # Try "text" mode first (reading order), fall back to "blocks"
            page_text = page.get_text("text").strip()

            # If "text" mode produces garbled output (common in two-column),
            # fall back to sorted blocks
            blocks = page.get_text("blocks")
            blocks_text = "\n\n".join(
                str(b[4]).strip()
                for b in sorted(blocks, key=lambda block: (round(block[1], 1), round(block[0], 1)))
                if str(b[4]).strip()
            )

            # Use the one with more readable content (fewer very short lines)
            text_lines = [l for l in page_text.splitlines() if l.strip()]
            blocks_lines = [l for l in blocks_text.splitlines() if l.strip()]
            text_avg = sum(len(l) for l in text_lines) / max(len(text_lines), 1)
            blocks_avg = sum(len(l) for l in blocks_lines) / max(len(blocks_lines), 1)

            # Prefer the extraction that has fewer very short lines, suggesting less fragmentation
            text_short_ratio = sum(1 for l in text_lines if len(l.strip()) < 15) / max(len(text_lines), 1)
            blocks_short_ratio = sum(1 for l in blocks_lines if len(l.strip()) < 15) / max(len(blocks_lines), 1)

            if text_short_ratio <= blocks_short_ratio and len(text_lines) >= len(blocks_lines) * 0.5:
                pages.append(page_text)
            else:
                pages.append(blocks_text)

        if total > 10:
            print(f"\r  page {total}/{total}...", end="", flush=True)
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
        if not line:
            lines.append("")
            continue
        if _looks_like_page_number(line):
            continue
        if _looks_like_header_footer(line):
            continue
        line = _fix_merged_words(line)
        line = _fix_drop_cap(line)
        line = _fix_math_unicode(line)
        lines.append(_promote_heading(line))

    # Post-process: merge single-letter lines with the next non-empty line
    lines = _merge_drop_cap_lines(lines)

    text = "\n".join(lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"\n{3}", "\n\n", text)
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


# ---- Header/Footer Noise Filter ----

_HEADER_FOOTER_PATTERNS: list[re.Pattern] = [
    # IEEE copyright & license
    re.compile(r"Authorized licensed use limited to"),
    re.compile(r"Downloaded on \w+ \d+, ?\d{4} at"),
    re.compile(r"©\s*\d{4}\s+IEEE"),
    re.compile(r"This article has been (accepted|published)"),
    re.compile(r"content may change prior to"),
    re.compile(r"DOI\s*10\.\d{4,}/"),
    re.compile(r"Personal use is permitted"),
    re.compile(r"Republication/redistribution requires"),
    re.compile(r"This work is licensed under"),
    re.compile(r"under a Creative Commons"),
    # Preprint notices
    re.compile(r"Preprint not peer reviewed"),
    re.compile(r"This preprint research paper has not been"),
    re.compile(r"SSRN:\s*\d+"),
    re.compile(r"Electronic copy available at"),
    # Journal metadata headers
    re.compile(r"^(IEEE )?(TRANSACTIONS|JOURNAL|LETTERS) ON [A-Z ]{10,}", re.IGNORECASE),
    re.compile(r"^VOL\.\s*\d+[,;]?\s*(NO\.?\s*\d+)?[,;]?\s*\d{4}$", re.IGNORECASE),
    re.compile(r"^(GENERIC COLORIZED JOURNAL|IEEE LATEX)", re.IGNORECASE),
    re.compile(r"^(AUTHOR et al\.?:|PREPARATION OF BRIEF PAPERS)", re.IGNORECASE),
    re.compile(r"^\d{5,}( \d{5,})*$"),  # Just long numbers (journal IDs)
    re.compile(r"^(npj |Nature |Scientific)"),  # Journal name headers
    re.compile(r"^\d{4} \d{1,2}:\d+$"),  # Like "2025 8:593"
    re.compile(r"Engineering Applications of"),
    re.compile(r"International Journal of"),
    re.compile(r"Computer Methods and Programs"),
    re.compile(r"ARTICLE IN PRESS"),
    re.compile(r"JID:\s*\w+"),
    re.compile(r"\[m5G;"),
    re.compile(r"Neural Networks \d+"),
    # Template boilerplate
    re.compile(r"^(IEEE TRANSACTIONS AND JOURNALS TEMPLATE)"),
    re.compile(r"^GENERIC COLORIZED JOURNAL"),
    re.compile(r"^\d{5,} \d{5,}$"),  # Long number pairs (journal IDs)
    # Page numbering artifacts
    re.compile(r"^1234567890[:,;]*\s*$"),
    re.compile(r"Page \d+ of \d+"),
]


def _looks_like_header_footer(line: str) -> bool:
    """Detect academic paper header/footer boilerplate."""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in _HEADER_FOOTER_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


# ---- Merged Words Fixer ----

_MERGED_WORD_SPLITS: list[tuple[str, str]] = [
    # Common ligature/merged word fixes from academic PDFs
    (r"([a-z]{2,})onthe([a-zA-Z])", r"\1 on the \2"),       # Buildingonthe...
    (r"([a-z]{2,})ofthe([a-zA-Z])", r"\1 of the \2"),
    (r"([a-z]{2,})inthe([a-zA-Z])", r"\1 in the \2"),
    (r"([a-z]{2,})andthe([a-zA-Z])", r"\1 and the \2"),
    (r"([a-z]{2,})tothe([a-zA-Z])", r"\1 to the \2"),
    (r"([a-z]{2,})forthe([a-zA-Z])", r"\1 for the \2"),
    (r"([a-z]{2,})withthe([a-zA-Z])", r"\1 with the \2"),
    (r"([a-z]{2,})fromthe([a-zA-Z])", r"\1 from the \2"),
    (r"([a-z]{2,})bythe([a-zA-Z])", r"\1 by the \2"),
    (r"([a-z]{2,})thatthe([a-zA-Z])", r"\1 that the \2"),
    (r"([a-z]{2,})asigni([a-z]+)", r"\1 a signi\2"),
    (r"([a-z]{2,})asub([a-z]+)", r"\1 a sub\2"),
    (r"([a-z]{2,})is([a-z]{3,})", r"\1 is \2"),
    (r"([a-z]{2,})are([a-z]{3,})", r"\1 are \2"),
    (r"([a-z]{2,})was([a-z]{3,})", r"\1 was \2"),
    (r"([a-z]{2,})were([a-z]{3,})", r"\1 were \2"),
    (r"([a-z]{2,})has([a-z]{3,})", r"\1 has \2"),
    (r"([a-z]{2,})have([a-z]{3,})", r"\1 have \2"),
    # Extreme merge: multi-word runs without spaces
    (r"Buildingonthefindingsof", "Building on the findings of"),
    (r"achievehigh", "achieve high"),
    (r"extremelyhigh", "extremely high"),
    (r"highabsorption", "high-absorption"),
    (r"Leeetal", "Lee et al"),
    (r"(et)al\.?(\d)", r"\1 al. \2"),  # etal.5 → et al. 5
    (r"(,)([a-zA-Z]{3,})", r"\1 \2"),  # 5,extremely → 5, extremely
]


def _fix_merged_words(line: str) -> str:
    """Heuristically split words that were merged during PDF extraction."""
    result = line
    for pattern, replacement in _MERGED_WORD_SPLITS:
        result = re.sub(pattern, replacement, result)
    return result


# ---- Drop-Cap Fixer ----

def _fix_drop_cap(line: str) -> str:
    """Fix drop-cap artifacts where a single letter precedes the rest of the paragraph."""
    stripped = line.strip()
    # Single capital letter followed by space and more text (but as separate lines)
    # We handle this in _merge_drop_cap_lines, just normalize here
    return line


def _merge_drop_cap_lines(lines: list[str]) -> list[str]:
    """Merge single-letter lines that are drop-cap artifacts into the next paragraph."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Single uppercase letter by itself on a line → merge with next non-empty line
        if len(stripped) == 1 and stripped.isupper() and stripped.isalpha():
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip():
                next_line = lines[j].strip()
                # Only merge if next line looks like continuation text (not a heading)
                if not next_line.startswith("#") and not next_line.startswith("## ") and len(next_line) > 5:
                    result.append(f"{stripped}{next_line}")
                    i = j + 1
                    continue
        result.append(line)
        i += 1
    return result


# ---- Math Unicode Fixer ----

_MATH_UNICODE_MAP: dict[str, str] = {
    # Common math symbols corrupted by PDF extraction
    "\uf02a": "∈",   # element of
    "\uf0b4": "×",   # multiplication
    "\uf0d7": "⊗",   # tensor product
    "\uf0e5": "∑",   # summation
    "\uf0b3": "≥",   # greater or equal
    "\uf0a3": "≤",   # less or equal
    "\uf061": "α",   # alpha
    "\uf062": "β",   # beta
    "\uf064": "δ",   # delta
    "\uf065": "ε",   # epsilon
    "\uf071": "θ",   # theta
    "\uf06d": "μ",   # mu
    "\uf072": "ρ",   # rho
    "\uf073": "σ",   # sigma
    "\uf074": "τ",   # tau
    "\uf066": "φ",   # phi
    "\uf077": "ω",   # omega
    "ϧ": "f",                   # ligature fi-like artifact
    # Combined dash artifact (must come before individual char replacements)
    "â\u02d8A\u0327S": "-A S", # "Blandâ˘A¸SAltman" → "Bland-ASAltman"
    "\u02d8": "",               # breve accent (˘)
    "\u0327": "",               # combining cedilla (¸)
    # Common ligatures
    "\ufb01": "fi",
    "\ufb02": "fl",
}


def _fix_math_unicode(line: str) -> str:
    """Replace corrupted Unicode math symbols with readable equivalents."""
    result = line
    for bad, good in _MATH_UNICODE_MAP.items():
        result = result.replace(bad, good)
    # Fix common PDF ligature spacing artifacts
    result = _fix_ligature_spacing(result)
    return result


_LIGATURE_FIXES: list[tuple[re.Pattern, str]] = [
    # Common academic words split by PDF font rendering
    (re.compile(r"\b(a)\s(ction)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(lysis)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(lyze[ds]?)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(e)\s(ction)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(i)\s(ction)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(u)\s(ction)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(tion)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(e)\s(tion)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(i)\s(tion)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(o)\s(tion)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(u)\s(tion)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(phic)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(phy)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(bly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(i)\s(ble)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(a)\s(ble)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(i)\s(cal)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(is)\s(hed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(is)\s(her)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(is)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(iz)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(iz)\s(ation)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(iz)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(c)\s(ally)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(t)\s(ically)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ic)\s(ally)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ment)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ment)\s(al)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ment)\s(ation)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(est)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(est)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ess)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ess)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(at)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(at)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(at)\s(ion)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(it)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(it)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ut)\s(ed)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ut)\s(ing)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ent)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ous)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ive)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ful)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(tic)\s(ally)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(al)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(an)\s(ce)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(en)\s(ce)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(an)\s(cy)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(an)\s(t)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(en)\s(t)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(er)\s(ent)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(or)\s(ent)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ar)\s(ent)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ur)\s(ent)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ir)\s(ent)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ab)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ib)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ub)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(eb)\s(ly)\b", re.IGNORECASE), r"\1\2"),
    (re.compile(r"\b(ob)\s(ly)\b", re.IGNORECASE), r"\1\2"),
]


def _fix_ligature_spacing(line: str) -> str:
    """Fix words split by PDF font ligature rendering."""
    result = line
    for pattern, replacement in _LIGATURE_FIXES:
        result = pattern.sub(replacement, result)
    return result


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
