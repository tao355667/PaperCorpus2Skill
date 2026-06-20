import json
from pathlib import Path

from papercorpus2skill.agent import PaperCorpus2SkillAgent
from papercorpus2skill.llm import BaseLLMProvider


class CountingProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        self.calls += 1
        return json.dumps(
            {
                "domain": "web development education",
                "purpose": "Help write web development education papers.",
                "terminology": {"preferred": ["progressive enhancement"], "avoid": []},
                "section_logic": {},
                "section_expressions": {"introduction": ["Prior work motivates resilient interfaces."]},
                "concept_threads": [
                    {
                        "concept": "progressive enhancement",
                        "problem_role": "Motivates resilient interface design.",
                        "method_role": "Structures implementation layers.",
                        "evidence_role": "Evaluated through constrained-use assignments.",
                        "discussion_role": "Interpreted as robustness evidence.",
                        "claim_strength": "moderate",
                        "common_transitions": ["This motivates a layered implementation strategy."],
                        "do_not_confuse_with": ["progressive web app"],
                        "section_roles": {"introduction": ["Frames the limitation."]},
                        "writing_guidance": ["Reuse the concept from motivation to evidence."],
                    }
                ],
            }
        )


def test_agent_persists_summaries_state_and_report_for_resume(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for index in range(6):
        (corpus / f"paper-{index}.md").write_text(
            f"# Paper {index}\n\n## Introduction\nText.\n\n## References\nNoise.",
            encoding="utf-8",
        )
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "outputs"

    first_provider = CountingProvider()
    first_pack = PaperCorpus2SkillAgent(first_provider).generate(
        input_path=corpus,
        output_dir=output_dir,
        target_tools=["universal"],
        create_zip=False,
        cache_dir=cache_dir,
        papers_per_batch=5,
        summaries_per_merge=5,
    )
    assert first_provider.calls == 3
    assert (cache_dir / "summaries" / "batch-000.json").exists()
    assert (cache_dir / "state" / "working-skill.json").exists()
    assert (first_pack.root / "corpus-report.md").exists()

    second_provider = CountingProvider()
    second_pack = PaperCorpus2SkillAgent(second_provider).generate(
        input_path=corpus,
        output_dir=output_dir,
        target_tools=["universal"],
        create_zip=False,
        cache_dir=cache_dir,
        papers_per_batch=5,
        summaries_per_merge=5,
    )
    assert second_provider.calls == 0
    assert second_pack.root == first_pack.root
