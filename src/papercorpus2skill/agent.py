from __future__ import annotations

from pathlib import Path

from papercorpus2skill.batch_analyzer import analyze_corpus_in_batches
from papercorpus2skill.corpus import discover_sources
from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.markdown_converter import MarkdownCacheConverter
from papercorpus2skill.parsers import ParsedDocument
from papercorpus2skill.skills import SkillPack, render_skill_pack


class NoSupportedFilesError(RuntimeError):
    pass


class PaperCorpus2SkillAgent:
    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    def generate(
        self,
        input_path: Path,
        output_dir: Path,
        skill_type: str = "academic_writing",
        target_tools: list[str] | None = None,
        include_zotero: bool = False,
        create_zip: bool = True,
        domain_hint: str | None = None,
        cache_dir: Path | None = None,
        papers_per_batch: int = 5,
        summaries_per_merge: int = 5,
        pdf_backend: str = "pymupdf",
    ) -> SkillPack:
        targets = target_tools or ["universal", "claude", "chatgpt", "codex", "cursor"]
        sources = discover_sources(input_path, include_zotero=include_zotero)
        if not sources:
            raise NoSupportedFilesError(f"No PDF or Markdown files found under {input_path}")

        resolved_output_dir = Path(output_dir).expanduser().resolve()
        resolved_cache_root = Path(cache_dir).expanduser().resolve() if cache_dir else resolved_output_dir / ".cache"
        markdown_cache_dir = resolved_cache_root / "markdown"
        markdown_docs = MarkdownCacheConverter(markdown_cache_dir, pdf_backend=pdf_backend).convert_many(sources)
        documents = [
            ParsedDocument(source=document.source, title=document.title, text=document.markdown)
            for document in markdown_docs
        ]
        guidance = analyze_corpus_in_batches(
            documents,
            self.provider,
            skill_type,
            domain_hint=domain_hint,
            papers_per_batch=papers_per_batch,
            summaries_per_merge=summaries_per_merge,
            cache_dir=resolved_cache_root,
        )
        pack = render_skill_pack(
            guidance=guidance,
            output_dir=resolved_output_dir,
            skill_type=skill_type,
            source_file_count=len(sources),
            target_tools=targets,
        )
        report = _corpus_report(
            source_count=len(sources),
            pdf_count=sum(1 for source in sources if source.kind == "pdf"),
            markdown_count=sum(1 for source in sources if source.kind == "markdown"),
            markdown_cache_dir=markdown_cache_dir,
            analysis_cache_dir=resolved_cache_root,
            papers_per_batch=papers_per_batch,
            summaries_per_merge=summaries_per_merge,
            pdf_backend=pdf_backend,
        )
        report_path = pack.root / "corpus-report.md"
        report_path.write_text(report, encoding="utf-8")
        pack.files.append(report_path)
        if create_zip:
            pack.zip()
        return pack


def _corpus_report(
    source_count: int,
    pdf_count: int,
    markdown_count: int,
    markdown_cache_dir: Path,
    analysis_cache_dir: Path,
    papers_per_batch: int,
    summaries_per_merge: int,
    pdf_backend: str,
) -> str:
    return "\n".join(
        [
            "# Corpus Report",
            "",
            f"- Source files: {source_count}",
            f"- PDF files: {pdf_count}",
            f"- Markdown files: {markdown_count}",
            f"- PDF backend: {pdf_backend}",
            f"- Papers per batch: {papers_per_batch}",
            f"- Summaries per merge: {summaries_per_merge}",
            f"- Markdown cache: `{markdown_cache_dir}`",
            f"- Analysis cache: `{analysis_cache_dir}`",
            "",
        ]
    )
