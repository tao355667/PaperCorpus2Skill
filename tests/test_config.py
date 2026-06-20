from pathlib import Path

from papercorpus2skill.config import AppConfig, load_config


def test_load_config_reads_nested_values_and_lists(tmp_path: Path) -> None:
    config_path = tmp_path / "papercorpus2skill.yaml"
    config_path.write_text(
        """
# Comments are ignored.
app:
  output_dir: ./custom-outputs
  cache_dir: ./.custom-cache

llm:
  provider: openai_compatible
  base_url: https://api.deepseek.com/v1
  api_key_env: DEEPSEEK_API_KEY
  model: deepseek-chat
  temperature: 0.1

generation:
  skill_type: academic_writing
  create_zip: false
  target_tools:
    - universal
    - codex

processing:
  papers_per_batch: 7
  summaries_per_merge: 3
  pdf_backend: pymupdf4llm
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.app.output_dir == Path("./custom-outputs")
    assert config.app.cache_dir == Path("./.custom-cache")
    assert config.llm.provider == "openai_compatible"
    assert config.llm.base_url == "https://api.deepseek.com/v1"
    assert config.llm.api_key_env == "DEEPSEEK_API_KEY"
    assert config.llm.model == "deepseek-chat"
    assert config.llm.temperature == 0.1
    assert config.generation.skill_type == "academic_writing"
    assert config.generation.create_zip is False
    assert config.generation.target_tools == ["universal", "codex"]
    assert config.processing.papers_per_batch == 7
    assert config.processing.summaries_per_merge == 3
    assert config.processing.pdf_backend == "pymupdf4llm"


def test_missing_config_uses_safe_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.yaml")

    assert config == AppConfig()
