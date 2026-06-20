from pathlib import Path

from papercorpus2skill.corpus import discover_sources


def test_discovers_pdf_and_markdown_recursively(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("# Paper\n", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (nested / "notes.txt").write_text("not supported", encoding="utf-8")

    sources = discover_sources(tmp_path)

    assert [(source.path.name, source.kind) for source in sources] == [
        ("paper.md", "markdown"),
        ("paper.pdf", "pdf"),
    ]


def test_discovers_local_zotero_storage_pdfs(tmp_path: Path) -> None:
    zotero_storage = tmp_path / "Zotero" / "storage" / "ABC123"
    zotero_storage.mkdir(parents=True)
    (zotero_storage / "downloaded.pdf").write_bytes(b"%PDF-1.4\n")

    sources = discover_sources(tmp_path / "Zotero", include_zotero=True)

    assert len(sources) == 1
    assert sources[0].path.name == "downloaded.pdf"
    assert sources[0].kind == "pdf"
