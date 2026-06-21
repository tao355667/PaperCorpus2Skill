import json
from pathlib import Path

from papercorpus2skill.batch_analyzer import analyze_corpus_in_batches
from papercorpus2skill.corpus import SourceFile
from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.parsers import ParsedDocument


class RecordingProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> str:
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        if "Merge these intermediate corpus summaries" in prompt:
            return json.dumps(
                {
                    "domain": "web development education",
                    "purpose": "Help write web development education papers.",
                    "section_expressions": {
                        "introduction": ["Recent studies increasingly emphasize platform primitives."],
                        "method": ["We organize the instructional sequence around platform primitives."],
                    },
                    "concept_threads": [
                        {
                            "concept": "progressive enhancement",
                            "aliases": ["layered enhancement"],
                            "section_roles": {
                                "introduction": ["Motivates resilient interface design."],
                                "method": ["Structures implementation from HTML to JavaScript."],
                            },
                            "writing_guidance": ["Introduce resilience first, then implementation layers."],
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "domain": "web development education",
                "purpose": "Help write web development education papers.",
                "section_expressions": {"method": ["We organize the instructional sequence around platform primitives."]},
                "concept_threads": [],
            }
        )


def _document(index: int, tmp_path: Path) -> ParsedDocument:
    return ParsedDocument(
        source=SourceFile(path=tmp_path / f"paper-{index}.md", kind="markdown"),
        title=f"Paper {index}",
        text=f"""# Paper {index}

## Introduction
Progressive enhancement motivates resilient web interfaces.

## Method
We organize the instructional sequence around semantic HTML, CSS, and JavaScript.

## References
Reference noise.
""",
    )


def test_analyze_corpus_in_batches_summarizes_and_merges(tmp_path: Path) -> None:
    provider = RecordingProvider()
    documents = [_document(index, tmp_path) for index in range(12)]

    guidance = analyze_corpus_in_batches(
        documents,
        provider,
        skill_type="academic_writing",
        domain_hint="webdev",
        papers_per_batch=5,
        summaries_per_merge=5,
    )

    assert len(provider.prompts) == 4
    assert sum("Summarize this batch of papers" in prompt for prompt in provider.prompts) == 3
    assert "Reference noise" not in "\n".join(provider.prompts)
    assert guidance.section_expressions["method"] == [
        "We organize the instructional sequence around platform primitives."
    ]
    assert guidance.concept_threads[0].concept == "progressive enhancement"
