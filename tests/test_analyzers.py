import json
from pathlib import Path

from papercorpus2skill.analyzers import analyze_corpus
from papercorpus2skill.corpus import SourceFile
from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.parsers import ParsedDocument


class CapturingProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.prompt = ""

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
        self.prompt = messages[-1]["content"]
        return json.dumps(
            {
                "domain": "web development education",
                "purpose": "Help write web development education papers.",
                "terminology": {"preferred": [], "avoid": []},
                "section_logic": {},
                "section_expressions": {
                    "introduction": ["prior work has increasingly emphasized"],
                    "method": ["we organize the instructional sequence around"],
                },
                "writing_patterns": [],
                "rewrite_rules": [],
                "ai_taste_checklist": [],
                "examples": [],
            }
        )


def test_analyzer_prompt_filters_references_and_asks_for_section_expressions(tmp_path: Path) -> None:
    provider = CapturingProvider()
    document = ParsedDocument(
        source=SourceFile(path=tmp_path / "paper.md", kind="markdown"),
        title="Paper",
        text="""## Introduction
Intro phrasing.

## References
Reference entry that should not reach the model.
""",
    )

    guidance = analyze_corpus([document], provider, "academic_writing")

    assert "Reference entry that should not reach the model" not in provider.prompt
    assert "section_expressions" in provider.prompt
    assert guidance.section_expressions["introduction"] == ["prior work has increasingly emphasized"]
