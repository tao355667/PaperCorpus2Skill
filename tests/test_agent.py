import json
from pathlib import Path

from papercorpus2skill.agent import PaperCorpus2SkillAgent
from papercorpus2skill.llm import BaseLLMProvider


class FakeProvider(BaseLLMProvider):
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
        assert messages
        return json.dumps(
            {
                "domain": "web development education",
                "purpose": "Help write and review web development papers.",
                "terminology": {
                    "preferred": ["client-side rendering", "progressive enhancement"],
                    "avoid": ["fancy web stuff"],
                },
                "section_logic": {
                    "Introduction": [
                        "Introduce the learning context.",
                        "Identify the tooling or pedagogy gap.",
                    ]
                },
                "writing_patterns": ["State limitations conservatively."],
                "rewrite_rules": [
                    {
                        "name": "Prefer precise technical verbs",
                        "less_preferred": ["make websites better"],
                        "preferred": ["improve page responsiveness"],
                    }
                ],
                "ai_taste_checklist": ["Avoid exaggerated novelty claims."],
                "examples": ["This approach improves page responsiveness under constrained networks."],
            }
        )


def test_agent_generates_skill_pack_from_markdown_folder(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "paper.md").write_text("# WebDev Study\n\nProgressive enhancement matters.", encoding="utf-8")
    output_dir = tmp_path / "outputs"

    pack = PaperCorpus2SkillAgent(provider=FakeProvider()).generate(
        input_path=corpus,
        output_dir=output_dir,
        skill_type="academic_writing",
        target_tools=["universal", "codex", "chatgpt", "claude", "cursor"],
    )

    assert pack.root.exists()
    assert (pack.root / "SKILL.md").read_text(encoding="utf-8").startswith("# web development education")
    assert (pack.root / "exports" / "codex" / "AGENTS.md").exists()
    assert (pack.root / "exports" / "chatgpt" / "project-instructions.md").exists()
    assert (pack.root / "exports" / "claude" / "SKILL.md").exists()
    assert (pack.root / "exports" / "cursor" / "corpus2skill.mdc").exists()
    assert (pack.root / "skill.json").exists()


class GenericDomainProvider(BaseLLMProvider):
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
        return json.dumps(
            {
                "domain": "academic_writing",
                "purpose": "Help write academic text.",
                "terminology": {"preferred": [], "avoid": []},
                "section_logic": {},
                "writing_patterns": [],
                "rewrite_rules": [],
                "ai_taste_checklist": [],
                "examples": [],
            }
        )


def test_agent_replaces_skill_type_domain_with_document_title(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "paper.md").write_text(
        "# Progressive Enhancement in Web Development Education\n\nBody.",
        encoding="utf-8",
    )

    pack = PaperCorpus2SkillAgent(provider=GenericDomainProvider()).generate(
        input_path=corpus,
        output_dir=tmp_path / "outputs",
        skill_type="academic_writing",
        target_tools=["universal"],
        create_zip=False,
    )

    assert pack.name == "progressive-enhancement-in-web-development-education-academic-writing-skill"
