from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from papercorpus2skill.agent import PaperCorpus2SkillAgent
from papercorpus2skill.corpus import discover_sources
from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.skills import SkillPack


@dataclass(frozen=True)
class CorpusGroup:
    name: str
    path: Path
    source_count: int


@dataclass(frozen=True)
class BatchSkillPack:
    group: CorpusGroup
    pack: SkillPack


@dataclass(frozen=True)
class BatchResult:
    items: list[BatchSkillPack]


class NoCorpusGroupsError(RuntimeError):
    pass


def discover_corpus_groups(input_root: Path) -> list[CorpusGroup]:
    root = Path(input_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Batch input root must be a directory: {input_root}")

    groups: list[CorpusGroup] = []
    for child in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        sources = discover_sources(child)
        if sources:
            groups.append(CorpusGroup(name=child.name, path=child, source_count=len(sources)))
    return groups


class BatchPaperCorpus2SkillAgent:
    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    def generate_all(
        self,
        input_root: Path,
        output_dir: Path,
        skill_type: str = "academic_writing",
        target_tools: list[str] | None = None,
        create_zip: bool = True,
        cache_dir: Path | None = None,
        papers_per_batch: int = 5,
        summaries_per_merge: int = 5,
        pdf_backend: str = "pymupdf",
    ) -> BatchResult:
        groups = discover_corpus_groups(input_root)
        if not groups:
            raise NoCorpusGroupsError(
                f"No corpus groups found under {input_root}. Create one subfolder per category and add PDF or Markdown files."
            )

        agent = PaperCorpus2SkillAgent(self.provider)
        items: list[BatchSkillPack] = []
        for group in groups:
            pack = agent.generate(
                input_path=group.path,
                output_dir=Path(output_dir) / group.name,
                skill_type=skill_type,
                target_tools=target_tools,
                include_zotero=False,
                create_zip=create_zip,
                domain_hint=group.name,
                cache_dir=(Path(cache_dir) / group.name) if cache_dir else None,
                papers_per_batch=papers_per_batch,
                summaries_per_merge=summaries_per_merge,
                pdf_backend=pdf_backend,
            )
            items.append(BatchSkillPack(group=group, pack=pack))
        return BatchResult(items=items)
