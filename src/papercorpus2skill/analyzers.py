from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from typing import Any

from papercorpus2skill.llm import BaseLLMProvider
from papercorpus2skill.parsers import ParsedDocument
from papercorpus2skill.sectioning import build_section_corpus


@dataclass(frozen=True)
class RewriteRule:
    name: str
    less_preferred: list[str] = field(default_factory=list)
    preferred: list[str] = field(default_factory=list)


@dataclass
class ConceptThread:
    concept: str
    aliases: list[str] = field(default_factory=list)
    section_roles: dict[str, list[str]] = field(default_factory=dict)
    writing_guidance: list[str] = field(default_factory=list)
    problem_role: str = ""
    method_role: str = ""
    evidence_role: str = ""
    discussion_role: str = ""
    claim_strength: str = ""
    common_transitions: list[str] = field(default_factory=list)
    do_not_confuse_with: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorpusGuidance:
    domain: str
    purpose: str
    terminology_preferred: list[str] = field(default_factory=list)
    terminology_avoid: list[str] = field(default_factory=list)
    section_logic: dict[str, list[str]] = field(default_factory=dict)
    section_expressions: dict[str, list[str]] = field(default_factory=dict)
    concept_threads: list[ConceptThread] = field(default_factory=list)
    writing_patterns: list[str] = field(default_factory=list)
    rewrite_rules: list[RewriteRule] = field(default_factory=list)
    ai_taste_checklist: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


def analyze_corpus(
    documents: list[ParsedDocument],
    provider: BaseLLMProvider,
    skill_type: str,
    temperature: float = 0.2,
    domain_hint: str | None = None,
) -> CorpusGuidance:
    messages = [
        {
            "role": "system",
            "content": (
                "You generate reusable AI writing skills from academic paper corpora. "
                "Do not copy corpus sentences verbatim. Return compact JSON only."
            ),
        },
        {
            "role": "user",
            "content": _build_prompt(documents, skill_type, domain_hint),
        },
    ]
    response = provider.chat(messages, temperature=temperature)
    guidance = guidance_from_json(response)
    if _same_label(guidance.domain, skill_type):
        return replace(guidance, domain=domain_hint or _infer_domain(documents))
    return guidance


def guidance_from_json(raw: str) -> CorpusGuidance:
    data = _loads_json_object(raw)
    terminology = data.get("terminology", {})
    return CorpusGuidance(
        domain=str(data.get("domain") or "paper corpus").strip(),
        purpose=str(data.get("purpose") or "Help write, revise, and review academic text.").strip(),
        terminology_preferred=_string_list(terminology.get("preferred")),
        terminology_avoid=_string_list(terminology.get("avoid")),
        section_logic=_section_logic(data.get("section_logic")),
        section_expressions=_section_logic(data.get("section_expressions")),
        concept_threads=_concept_threads(data.get("concept_threads")),
        writing_patterns=_string_list(data.get("writing_patterns")),
        rewrite_rules=[
            RewriteRule(
                name=str(rule.get("name") or "Rewrite rule"),
                less_preferred=_string_list(rule.get("less_preferred")),
                preferred=_string_list(rule.get("preferred")),
            )
            for rule in data.get("rewrite_rules", [])
            if isinstance(rule, dict)
        ],
        ai_taste_checklist=_string_list(data.get("ai_taste_checklist")),
        examples=_string_list(data.get("examples")),
    )


def _build_prompt(documents: list[ParsedDocument], skill_type: str, domain_hint: str | None) -> str:
    section_corpus = build_section_corpus(documents)
    excerpts = []
    for section, values in section_corpus.sections.items():
        joined = "\n\n".join(f"- {value}" for value in values[:20])
        excerpts.append(f"SECTION: {section}\n{joined}")

    return (
        f"Generate a {skill_type} skill from this paper corpus.\n"
        + (f"Corpus category: {domain_hint}\n" if domain_hint else "")
        +
        "The domain must describe the corpus subject, not the skill type.\n"
        f"The corpus contains {section_corpus.document_count} parsed documents. References have been removed locally.\n"
        "Return a JSON object with keys: domain, purpose, terminology {preferred, avoid}, "
        "section_logic, section_expressions, concept_threads, writing_patterns, rewrite_rules, ai_taste_checklist, examples.\n"
        "For section_expressions, summarize common academic expressions separately for abstract, introduction, "
        "related_work, method, experiments, discussion, and conclusion when evidence exists.\n"
        "For concept_threads, include problem_role, method_role, evidence_role, discussion_role, claim_strength, "
        "common_transitions, do_not_confuse_with, section_roles, and writing_guidance.\n"
        "Keep all lists concise and avoid copying full sentences from the corpus.\n\n"
        + "\n\n---\n\n".join(excerpts)
    )


def _loads_json_object(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1)
    return json.loads(stripped)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _section_logic(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {str(section): _string_list(steps) for section, steps in value.items()}


def _concept_threads(value: Any) -> list[ConceptThread]:
    if not isinstance(value, list):
        return []
    threads: list[ConceptThread] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept") or "").strip()
        if not concept:
            continue
        threads.append(
            ConceptThread(
                concept=concept,
                aliases=_string_list(item.get("aliases")),
                section_roles=_section_logic(item.get("section_roles")),
                writing_guidance=_string_list(item.get("writing_guidance")),
                problem_role=str(item.get("problem_role") or "").strip(),
                method_role=str(item.get("method_role") or "").strip(),
                evidence_role=str(item.get("evidence_role") or "").strip(),
                discussion_role=str(item.get("discussion_role") or "").strip(),
                claim_strength=str(item.get("claim_strength") or "").strip(),
                common_transitions=_string_list(item.get("common_transitions")),
                do_not_confuse_with=_string_list(item.get("do_not_confuse_with")),
            )
        )
    return threads


def _same_label(left: str, right: str) -> bool:
    normalize = lambda value: re.sub(r"[^a-z0-9]+", "", value.lower())
    return normalize(left) == normalize(right)


def _infer_domain(documents: list[ParsedDocument]) -> str:
    for document in documents:
        if document.title.strip():
            return document.title.strip()
    return "paper corpus"
