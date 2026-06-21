import json
from pathlib import Path

from papercorpus2skill.batch import BatchPaperCorpus2SkillAgent, discover_corpus_groups
from papercorpus2skill.llm import BaseLLMProvider


class BatchFakeProvider(BaseLLMProvider):
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
        prompt = messages[-1]["content"]
        if "Corpus category: webdev" in prompt:
            domain = "web development education"
        elif "Corpus category: nlp" in prompt:
            domain = "natural language processing"
        else:
            domain = "paper corpus"
        return json.dumps(
            {
                "domain": domain,
                "purpose": f"Help write academic text about {domain}.",
                "terminology": {"preferred": [domain], "avoid": []},
                "section_logic": {},
                "writing_patterns": [],
                "rewrite_rules": [],
                "ai_taste_checklist": [],
                "examples": [],
            }
        )


def test_discovers_each_top_level_folder_as_a_corpus_group(tmp_path: Path) -> None:
    (tmp_path / "webdev").mkdir()
    (tmp_path / "webdev" / "paper.md").write_text("# WebDev\n\nBody", encoding="utf-8")
    (tmp_path / "nlp").mkdir()
    (tmp_path / "nlp" / "paper.md").write_text("# NLP\n\nBody", encoding="utf-8")
    (tmp_path / "empty").mkdir()
    (tmp_path / "root-paper.md").write_text("# Ignored by batch grouping\n", encoding="utf-8")

    groups = discover_corpus_groups(tmp_path)

    assert [(group.name, group.path.name, group.source_count) for group in groups] == [
        ("nlp", "nlp", 1),
        ("webdev", "webdev", 1),
    ]


def test_batch_agent_generates_one_skill_pack_per_group(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    (corpus_root / "webdev").mkdir(parents=True)
    (corpus_root / "webdev" / "paper.md").write_text("# WebDev\n\nBody", encoding="utf-8")
    (corpus_root / "nlp").mkdir()
    (corpus_root / "nlp" / "paper.md").write_text("# NLP\n\nBody", encoding="utf-8")

    result = BatchPaperCorpus2SkillAgent(provider=BatchFakeProvider()).generate_all(
        input_root=corpus_root,
        output_dir=tmp_path / "outputs",
        skill_type="academic_writing",
        target_tools=["universal", "codex"],
        create_zip=False,
    )

    assert [item.group.name for item in result.items] == ["nlp", "webdev"]
    assert [item.pack.name for item in result.items] == [
        "natural-language-processing-academic-writing-skill",
        "web-development-education-academic-writing-skill",
    ]
    assert (tmp_path / "outputs" / "nlp" / "natural-language-processing-academic-writing-skill").exists()
    assert (tmp_path / "outputs" / "webdev" / "web-development-education-academic-writing-skill").exists()
