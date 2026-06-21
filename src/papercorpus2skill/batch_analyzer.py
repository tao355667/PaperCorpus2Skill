from __future__ import annotations

import json
import re
from pathlib import Path

from papercorpus2skill.analyzers import chat_for_json, guidance_from_json
from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.parsers import ParsedDocument
from papercorpus2skill.sectioning import build_section_corpus
from papercorpus2skill.skill_state import SkillState, SummaryChunk, load_summary, save_state, save_summary, summary_to_dict


def analyze_corpus_in_batches(
    documents: list[ParsedDocument],
    provider: BaseLLMProvider,
    skill_type: str,
    temperature: float = 0.2,
    domain_hint: str | None = None,
    papers_per_batch: int = 5,
    summaries_per_merge: int = 5,
    cache_dir: Path | None = None,
) -> object:
    state = SkillState(domain=domain_hint or "paper corpus")
    summaries: list[SummaryChunk] = []
    cache = Path(cache_dir) if cache_dir else None

    batches = _chunks(documents, papers_per_batch)
    total_batches = len(batches)
    for batch_index, batch in enumerate(batches):
        summary_path = cache / "summaries" / f"batch-{batch_index:03d}.json" if cache else None
        cached = summary_path and summary_path.exists()
        if cached:
            print(f"  Batch {batch_index + 1}/{total_batches} (cached, {len(batch)} papers)")
        else:
            print(f"  Batch {batch_index + 1}/{total_batches}: Summarizing {len(batch)} papers...", flush=True)
        summary = _load_or_create_summary(
            summary_path,
            lambda batch=batch: _summarize_papers(batch, provider, skill_type, temperature, domain_hint),
        )
        if not cached:
            print(f"    done.")
        state.apply_summary(summary)
        _save_working_state(cache, state)
        summaries.append(summary)

    current = summaries
    round_index = 1
    while len(current) > 1:
        groups = _chunks(current, summaries_per_merge)
        print(f"  Merge round {round_index}: merging {len(current)} summaries into {len(groups)}...", flush=True)
        merged: list[SummaryChunk] = []
        for group_index, group in enumerate(groups):
            summary_path = cache / "summaries" / f"merge-r{round_index:02d}-{group_index:03d}.json" if cache else None
            cached = summary_path and summary_path.exists()
            if cached:
                print(f"    Group {group_index + 1}/{len(groups)} (cached)")
            summary = _load_or_create_summary(
                summary_path,
                lambda group=group: _merge_summaries(group, provider, skill_type, temperature, domain_hint),
            )
            if not cached:
                print(f"    Group {group_index + 1}/{len(groups)} done.")
            state.apply_summary(summary)
            _save_working_state(cache, state)
            merged.append(summary)
        current = merged
        round_index += 1

    if _same_label(state.domain, skill_type):
        state.domain = domain_hint or _infer_domain(documents)
    _save_working_state(cache, state)
    return state.to_guidance()


def _summarize_papers(
    documents: list[ParsedDocument],
    provider: BaseLLMProvider,
    skill_type: str,
    temperature: float,
    domain_hint: str | None,
) -> SummaryChunk:
    prompt = _paper_batch_prompt(documents, skill_type, domain_hint)
    response = chat_for_json(provider, _messages(prompt), temperature=temperature)
    return _summary_from_response(response)


def _merge_summaries(
    summaries: list[SummaryChunk],
    provider: BaseLLMProvider,
    skill_type: str,
    temperature: float,
    domain_hint: str | None,
) -> SummaryChunk:
    prompt = _merge_prompt(summaries, skill_type, domain_hint)
    response = chat_for_json(provider, _messages(prompt), temperature=temperature)
    return _summary_from_response(response)


def _paper_batch_prompt(documents: list[ParsedDocument], skill_type: str, domain_hint: str | None) -> str:
    corpus = build_section_corpus(documents, max_documents=len(documents), max_chars_per_section_per_doc=5000)
    sections = []
    for section, values in corpus.sections.items():
        sections.append(f"SECTION: {section}\n" + "\n\n".join(f"- {value}" for value in values))
    return (
        f"Summarize this batch of papers for a {skill_type} skill.\n"
        + (f"Corpus category: {domain_hint}\n" if domain_hint else "")
        + f"Batch size: {len(documents)} papers. References have already been removed.\n"
        "Extract two complementary views:\n"
        "1. Section-level expressions: common expressions and rhetorical moves shared by the same section across papers.\n"
        "2. Paper-level concept threads: how the same module, dataset, metric, result, or technical concept is described across sections within a paper.\n"
        "Return compact JSON with keys: domain, purpose, terminology {preferred, avoid}, section_logic, "
        "section_expressions, concept_threads, writing_patterns, rewrite_rules, ai_taste_checklist, examples.\n"
        "concept_threads items must include: concept, aliases, problem_role, method_role, evidence_role, "
        "discussion_role, claim_strength, common_transitions, do_not_confuse_with, section_roles, writing_guidance.\n"
        "rewrite_rules: extract domain-specific academic revision patterns observed across papers, e.g., "
        "'replace vague novelty claims (novel, state-of-the-art) with specific technical distinctions', "
        "'prefer metric-backed comparisons (outperforms X by Y bpm) over qualitative claims', "
        "'replace passive voice with active when describing method design choices'.\n"
        "Do not copy full source sentences verbatim.\n\n"
        + "\n\n---\n\n".join(sections)
    )


def _merge_prompt(summaries: list[SummaryChunk], skill_type: str, domain_hint: str | None) -> str:
    payload = [_summary_to_dict(summary) for summary in summaries]
    return (
        f"Merge these intermediate corpus summaries into a stronger {skill_type} skill state.\n"
        + (f"Corpus category: {domain_hint}\n" if domain_hint else "")
        + "Merge equivalent expressions, combine similar concept threads, preserve section-level and paper-level guidance, "
        "and remove generic or duplicated items.\n"
        "Return compact JSON with keys: domain, purpose, terminology {preferred, avoid}, section_logic, "
        "section_expressions, concept_threads, writing_patterns, rewrite_rules, ai_taste_checklist, examples.\n"
        "Preserve problem_role, method_role, evidence_role, discussion_role, claim_strength, common_transitions, "
        "and do_not_confuse_with in concept_threads.\n"
        "For rewrite_rules: merge and deduplicate, keep only domain-specific academic revision rules "
        "(e.g., 'use metric-backed comparisons', 'replace vague novelty claims with technical distinctions').\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _summary_from_response(raw: str) -> SummaryChunk:
    guidance = guidance_from_json(raw)
    return SummaryChunk(
        domain=guidance.domain,
        purpose=guidance.purpose,
        terminology_preferred=guidance.terminology_preferred,
        terminology_avoid=guidance.terminology_avoid,
        section_logic=guidance.section_logic,
        section_expressions=guidance.section_expressions,
        concept_threads=guidance.concept_threads,
        writing_patterns=guidance.writing_patterns,
        rewrite_rules=guidance.rewrite_rules,
        ai_taste_checklist=guidance.ai_taste_checklist,
        examples=guidance.examples,
    )


def _summary_to_dict(summary: SummaryChunk) -> dict:
    return summary_to_dict(summary)


def _messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You extract reusable academic writing skills from paper corpora. "
                "Focus on section-level expressions and paper-level concept threads. Return JSON only."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def _chunks(items: list, size: int) -> list[list]:
    if size < 1:
        raise ValueError("Chunk size must be at least 1")
    return [items[index : index + size] for index in range(0, len(items), size)]


def _load_or_create_summary(path: Path | None, create: object) -> SummaryChunk:
    if path and path.exists():
        return load_summary(path)
    summary = create()
    if path:
        save_summary(path, summary)
    return summary


def _save_working_state(cache: Path | None, state: SkillState) -> None:
    if cache:
        save_state(cache / "state" / "working-skill.json", state)


def _same_label(left: str, right: str) -> bool:
    normalize = lambda value: re.sub(r"[^a-z0-9]+", "", value.lower())
    return normalize(left) == normalize(right)


def _infer_domain(documents: list[ParsedDocument]) -> str:
    for document in documents:
        if document.title.strip():
            return document.title.strip()
    return "paper corpus"
