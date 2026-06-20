from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppSection:
    output_dir: Path = Path("outputs")
    cache_dir: Path = Path(".papercorpus2skill/cache")


@dataclass(frozen=True)
class LLMSection:
    provider: str = "openai_compatible"
    base_url: str | None = None
    api_key_env: str | None = None
    model: str | None = None
    temperature: float = 0.2


@dataclass(frozen=True)
class GenerationSection:
    skill_type: str = "academic_writing"
    target_tools: list[str] = field(default_factory=lambda: ["universal", "claude", "chatgpt", "codex", "cursor"])
    create_zip: bool = True


@dataclass(frozen=True)
class ProcessingSection:
    papers_per_batch: int = 5
    summaries_per_merge: int = 5
    pdf_backend: str = "pymupdf"


@dataclass(frozen=True)
class AppConfig:
    app: AppSection = field(default_factory=AppSection)
    llm: LLMSection = field(default_factory=LLMSection)
    generation: GenerationSection = field(default_factory=GenerationSection)
    processing: ProcessingSection = field(default_factory=ProcessingSection)


class ConfigError(RuntimeError):
    pass


def load_config(path: Path = Path("papercorpus2skill.yaml")) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()

    raw = _parse_simple_yaml(config_path.read_text(encoding="utf-8"))
    app = raw.get("app", {})
    llm = raw.get("llm", {})
    generation = raw.get("generation", {})
    processing = raw.get("processing", {})

    return AppConfig(
        app=AppSection(
            output_dir=Path(str(app.get("output_dir", "outputs"))),
            cache_dir=Path(str(app.get("cache_dir", ".papercorpus2skill/cache"))),
        ),
        llm=LLMSection(
            provider=str(llm.get("provider", "openai_compatible")),
            base_url=_optional_str(llm.get("base_url")),
            api_key_env=_optional_str(llm.get("api_key_env")),
            model=_optional_str(llm.get("model")),
            temperature=float(llm.get("temperature", 0.2)),
        ),
        generation=GenerationSection(
            skill_type=str(generation.get("skill_type", "academic_writing")),
            target_tools=[str(item) for item in generation.get("target_tools", GenerationSection().target_tools)],
            create_zip=bool(generation.get("create_zip", True)),
        ),
        processing=ProcessingSection(
            papers_per_batch=int(processing.get("papers_per_batch", 5)),
            summaries_per_merge=int(processing.get("summaries_per_merge", 5)),
            pdf_backend=str(processing.get("pdf_backend", "pymupdf")),
        ),
    )


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_section: str | None = None
    current_list_key: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            current_list_key = None
            result.setdefault(current_section, {})
            continue

        if current_section is None:
            raise ConfigError(f"Invalid config line {line_number}: expected a top-level section")

        section = result[current_section]
        if not isinstance(section, dict):
            raise ConfigError(f"Invalid config line {line_number}: section is not a mapping")

        if stripped.startswith("- "):
            if current_list_key is None:
                raise ConfigError(f"Invalid config line {line_number}: list item without a key")
            section.setdefault(current_list_key, []).append(_parse_scalar(stripped[2:].strip()))
            continue

        if ":" not in stripped:
            raise ConfigError(f"Invalid config line {line_number}: expected key: value")

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            section[key] = []
            current_list_key = key
        else:
            section[key] = _parse_scalar(value)
            current_list_key = None

    return result


def _strip_comment(line: str) -> str:
    in_quote: str | None = None
    for index, char in enumerate(line):
        if char in {"'", '"'}:
            in_quote = None if in_quote == char else char
        if char == "#" and in_quote is None:
            return line[:index]
    return line


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
