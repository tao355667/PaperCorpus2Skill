from pathlib import Path

from papercorpus2skill.env import load_dotenv
from papercorpus2skill.llm import LLMConfig


def test_load_dotenv_populates_missing_environment_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("DEEPSEEK_API_KEY=local-secret\n", encoding="utf-8")

    load_dotenv(env_path)

    assert LLMConfig(provider="openai_compatible", model="deepseek-chat", api_key_env="DEEPSEEK_API_KEY").resolved_api_key == "local-secret"


def test_load_dotenv_does_not_override_existing_environment_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "existing-secret")
    env_path = tmp_path / ".env"
    env_path.write_text("DEEPSEEK_API_KEY=local-secret\n", encoding="utf-8")

    load_dotenv(env_path)

    assert LLMConfig(provider="openai_compatible", model="deepseek-chat", api_key_env="DEEPSEEK_API_KEY").resolved_api_key == "existing-secret"
