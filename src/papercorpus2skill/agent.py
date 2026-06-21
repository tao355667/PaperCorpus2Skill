from __future__ import annotations

from pathlib import Path

from papercorpus2skill.batch_analyzer import analyze_corpus_in_batches
from papercorpus2skill.corpus import discover_sources
from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.markdown_converter import MarkdownCacheConverter, MarkdownDocument, _title_from_markdown
from papercorpus2skill.parsers import ParsedDocument
from papercorpus2skill.skills import SkillPack, render_skill_pack


class NoSupportedFilesError(RuntimeError):
    pass


class MarkdownCacheMissingError(RuntimeError):
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
        skip_convert: bool = False,
    ) -> SkillPack:
        targets = target_tools or ["universal", "claude", "chatgpt", "codex", "cursor"]
        sources = discover_sources(input_path, include_zotero=include_zotero)
        if not sources:
            raise NoSupportedFilesError(f"No PDF or Markdown files found under {input_path}")

        resolved_output_dir = Path(output_dir).expanduser().resolve()
        resolved_cache_root = Path(cache_dir).expanduser().resolve() if cache_dir else resolved_output_dir / ".cache"
        markdown_cache_dir = resolved_cache_root / "markdown"

        label = f"[{domain_hint}]" if domain_hint else ""

        if skip_convert:
            print(f"\n{label} Phase 1/3: Reading Markdown from corpus ({len(sources)} papers)...")
            markdown_docs = _load_markdowns_from_corpus(sources)
        else:
            print(f"\n{label} Phase 1/3: Converting {len(sources)} papers to Markdown...")
            markdown_docs = MarkdownCacheConverter(markdown_cache_dir, pdf_backend=pdf_backend).convert_many(sources)

        documents = [
            ParsedDocument(source=document.source, title=document.title, text=document.markdown)
            for document in markdown_docs
        ]

        total_batches = (len(documents) + papers_per_batch - 1) // papers_per_batch
        print(f"{label} Phase 2/3: Analyzing corpus ({len(documents)} papers in {total_batches} batches)...")
        guidance = analyze_corpus_in_batches(
            documents,
            self.provider,
            skill_type,
            domain_hint=domain_hint,
            papers_per_batch=papers_per_batch,
            summaries_per_merge=summaries_per_merge,
            cache_dir=resolved_cache_root,
        )
        print(f"{label} Phase 3/3: Rendering skill pack...")
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


def _load_markdowns_from_corpus(sources: list) -> list[MarkdownDocument]:
    """Read .md files from the markdown/ subdirectory in the corpus folder."""
    missing: list[str] = []
    docs: list[MarkdownDocument] = []
    for source in sources:
        # Look in corpus/{group}/markdown/{stem}.md
        md_path = source.path.parent / "markdown" / f"{source.path.stem}.md"
        if md_path.exists():
            markdown = md_path.read_text(encoding="utf-8")
            docs.append(MarkdownDocument(
                source=source,
                title=_title_from_markdown(source.path, markdown),
                markdown_path=md_path,
                markdown=markdown,
            ))
            print(f"  {source.path.name}")
        else:
            missing.append(str(source.path.name))
    if missing:
        raise MarkdownCacheMissingError(
            f"Markdown missing for {len(missing)} file(s). "
            f"Run `papercorpus2skill convert` first:\n  " + "\n  ".join(missing)
        )
    return docs


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
