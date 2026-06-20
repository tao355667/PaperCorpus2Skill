from pathlib import Path

from papercorpus2skill.corpus import SourceFile
from papercorpus2skill.parsers import ParsedDocument
from papercorpus2skill.sectioning import build_section_corpus, strip_references


def test_strip_references_removes_reference_tail() -> None:
    text = """Abstract
Useful abstract.

Introduction
Useful introduction.

References
[1] A copied reference title.
[2] Another copied reference title.
"""

    assert strip_references(text) == "Abstract\nUseful abstract.\n\nIntroduction\nUseful introduction."


def test_build_section_corpus_groups_common_paper_sections(tmp_path: Path) -> None:
    document = ParsedDocument(
        source=SourceFile(path=tmp_path / "paper.md", kind="markdown"),
        title="Paper",
        text="""# Paper

## Abstract
Abstract language.

## Introduction
Intro expression one.

## Method
Method expression one.

## References
Reference noise.
""",
    )

    corpus = build_section_corpus([document])

    assert corpus.document_count == 1
    assert corpus.sections["abstract"] == ["Abstract language."]
    assert corpus.sections["introduction"] == ["Intro expression one."]
    assert corpus.sections["method"] == ["Method expression one."]
    assert "references" not in corpus.sections
