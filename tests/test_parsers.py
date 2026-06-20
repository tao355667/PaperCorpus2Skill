from pathlib import Path

from papercorpus2skill.corpus import SourceFile
from papercorpus2skill.parsers import parse_source


def test_parses_markdown_as_document(tmp_path: Path) -> None:
    source_path = tmp_path / "sample-paper.md"
    source_path.write_text("# Sample Paper\n\nThis is the abstract.", encoding="utf-8")

    document = parse_source(SourceFile(path=source_path, kind="markdown"))

    assert document.title == "Sample Paper"
    assert "This is the abstract." in document.text
    assert document.source.path == source_path
