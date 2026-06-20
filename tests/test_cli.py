import subprocess
import sys
from pathlib import Path


def test_cli_preview_reports_supported_files(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "paper.md").write_text("# Paper\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "papercorpus2skill.cli.main", "preview", str(corpus)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Files detected: 1" in result.stdout
    assert "Markdown files: 1" in result.stdout


def test_cli_batch_preview_reports_corpus_groups(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    (corpus / "webdev").mkdir(parents=True)
    (corpus / "webdev" / "paper.md").write_text("# Paper\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "papercorpus2skill.cli.main", "batch-preview", str(corpus)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Corpus groups detected: 1" in result.stdout
    assert "webdev: 1 files" in result.stdout


def test_cli_batch_accepts_model_settings_from_config(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    (corpus / "webdev").mkdir(parents=True)
    (corpus / "webdev" / "paper.md").write_text("# Paper\n", encoding="utf-8")
    config = tmp_path / "papercorpus2skill.yaml"
    config.write_text(
        """
app:
  output_dir: ./outputs
llm:
  provider: unsupported_for_test
  model: configured-model
generation:
  target_tools:
    - universal
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "papercorpus2skill.cli.main",
            "--config",
            str(config),
            "batch",
            str(corpus),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Unsupported LLM provider: unsupported_for_test" in result.stderr
