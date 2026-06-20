from pathlib import Path

from papercorpus2skill.corpus import SourceFile
from papercorpus2skill.markdown_converter import MarkdownCacheConverter, PDFBackendError


def test_markdown_converter_caches_markdown_sources(tmp_path: Path) -> None:
    source = tmp_path / "paper.md"
    source.write_text("# Paper\n\n## References\nNoise", encoding="utf-8")
    converter = MarkdownCacheConverter(cache_dir=tmp_path / "cache")

    document = converter.convert(SourceFile(path=source, kind="markdown"))

    assert document.title == "Paper"
    assert document.markdown_path.exists()
    assert document.markdown_path.read_text(encoding="utf-8").startswith("# Paper")


def test_markdown_converter_rejects_unknown_pdf_backend(tmp_path: Path) -> None:
    converter = MarkdownCacheConverter(cache_dir=tmp_path / "cache", pdf_backend="unknown")

    try:
        converter.convert(SourceFile(path=tmp_path / "paper.pdf", kind="pdf"))
    except PDFBackendError as exc:
        assert "Unsupported PDF backend" in str(exc)
    else:
        raise AssertionError("Expected PDFBackendError")
