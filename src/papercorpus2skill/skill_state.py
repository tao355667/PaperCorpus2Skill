from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from papercorpus2skill.analyzers import ConceptThread, CorpusGuidance, RewriteRule


@dataclass(frozen=True)
class SectionExpression:
    text: str
    count: int = 1


@dataclass
class SummaryChunk:
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


@dataclass
class SkillState:
    domain: str
    purpose: str = "Help write, revise, and review academic text."
    terminology_preferred: list[str] = field(default_factory=list)
    terminology_avoid: list[str] = field(default_factory=list)
    section_logic: dict[str, list[str]] = field(default_factory=dict)
    section_expressions: dict[str, list[SectionExpression]] = field(default_factory=dict)
    concept_threads: list[ConceptThread] = field(default_factory=list)
    writing_patterns: list[str] = field(default_factory=list)
    rewrite_rules: list[RewriteRule] = field(default_factory=list)
    ai_taste_checklist: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def apply_summary(self, summary: SummaryChunk) -> None:
        if summary.domain and _is_more_specific(summary.domain, self.domain):
            self.domain = summary.domain
        if summary.purpose:
            self.purpose = summary.purpose
        _extend_unique(self.terminology_preferred, summary.terminology_preferred)
        _extend_unique(self.terminology_avoid, summary.terminology_avoid)
        _merge_section_lists(self.section_logic, summary.section_logic)
        self._merge_section_expressions(summary.section_expressions)
        self._merge_concept_threads(summary.concept_threads)
        _extend_unique(self.writing_patterns, summary.writing_patterns)
        self._merge_rewrite_rules(summary.rewrite_rules)
        _extend_unique(self.ai_taste_checklist, summary.ai_taste_checklist)
        _extend_unique(self.examples, summary.examples)

    def to_guidance(self) -> CorpusGuidance:
        return CorpusGuidance(
            domain=self.domain,
            purpose=self.purpose,
            terminology_preferred=self.terminology_preferred,
            terminology_avoid=self.terminology_avoid,
            section_logic=self.section_logic,
            section_expressions={
                section: [expression.text for expression in sorted(expressions, key=lambda item: (-item.count, item.text.lower()))]
                for section, expressions in self.section_expressions.items()
            },
            concept_threads=self.concept_threads,
            writing_patterns=self.writing_patterns,
            rewrite_rules=self.rewrite_rules,
            ai_taste_checklist=self.ai_taste_checklist,
            examples=self.examples,
        )

    def _merge_section_expressions(self, incoming: dict[str, list[str]]) -> None:
        for section, values in incoming.items():
            expressions = self.section_expressions.setdefault(section, [])
            index = {_norm(expression.text): offset for offset, expression in enumerate(expressions)}
            for value in values:
                text = value.strip()
                if not text:
                    continue
                key = _norm(text)
                if key in index:
                    old = expressions[index[key]]
                    expressions[index[key]] = SectionExpression(text=old.text, count=old.count + 1)
                else:
                    index[key] = len(expressions)
                    expressions.append(SectionExpression(text=text, count=1))

    def _merge_concept_threads(self, incoming: list[ConceptThread]) -> None:
        for thread in incoming:
            key = _norm(thread.concept)
            if not key:
                continue
            current = self._find_matching_thread(key)
            if current is None:
                current = ConceptThread(concept=thread.concept.strip(), aliases=[], section_roles={}, writing_guidance=[])
                self.concept_threads.append(current)
            _extend_unique(current.aliases, thread.aliases)
            _merge_section_lists(current.section_roles, thread.section_roles)
            _extend_unique(current.writing_guidance, thread.writing_guidance)
            current.problem_role = current.problem_role or thread.problem_role
            current.method_role = current.method_role or thread.method_role
            current.evidence_role = current.evidence_role or thread.evidence_role
            current.discussion_role = current.discussion_role or thread.discussion_role
            current.claim_strength = current.claim_strength or thread.claim_strength
            _extend_unique_transitions(current.common_transitions, thread.common_transitions)
            _extend_unique(current.do_not_confuse_with, thread.do_not_confuse_with)

    def _find_matching_thread(self, key: str) -> ConceptThread | None:
        """Find an existing concept thread matching ``key``.

        A substring match is used (in addition to exact match) so that
        ``computational efficiency`` and ``computational efficiency lightweight design``
        are recognized as the same concept. The shorter key must be at least
        5 characters to avoid false positives on very short tokens.
        """
        for thread in self.concept_threads:
            existing = _norm(thread.concept)
            if key == existing:
                return thread
            if len(key) >= 5 and (key in existing or existing in key):
                return thread
        return None

    def _merge_rewrite_rules(self, incoming: list[RewriteRule]) -> None:
        existing = {_norm(rule.name): rule for rule in self.rewrite_rules}
        for rule in incoming:
            key = _norm(rule.name)
            if key in existing:
                current = existing[key]
                _extend_unique(current.less_preferred, rule.less_preferred)
                _extend_unique(current.preferred, rule.preferred)
            else:
                self.rewrite_rules.append(rule)
                existing[key] = rule


def _extend_unique(target: list[str], values: list[str]) -> None:
    seen = {_norm(item) for item in target}
    for value in values:
        text = value.strip()
        key = _norm(text)
        if text and key not in seen:
            target.append(text)
            seen.add(key)


def _extend_unique_transitions(target: list[str], values: list[str]) -> None:
    """Deduplicate common_transitions, ignoring ``From X to Y:`` prefixes."""
    seen = {_norm_transition(item) for item in target}
    for value in values:
        text = value.strip()
        key = _norm_transition(text)
        if text and key not in seen:
            target.append(text)
            seen.add(key)


_TRANSITION_PREFIX_RE = re.compile(r"^\s*From\s+\w+\s+to\s+\w+\s*:\s*", re.IGNORECASE)


def _norm_transition(value: str) -> str:
    stripped = _TRANSITION_PREFIX_RE.sub("", value)
    return _norm(stripped)


def _merge_section_lists(target: dict[str, list[str]], incoming: dict[str, list[str]]) -> None:
    for section, values in incoming.items():
        bucket = target.setdefault(section, [])
        _extend_unique(bucket, values)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value.lower()).strip()


def _is_more_specific(candidate: str, current: str) -> bool:
    if not current or current == "paper corpus":
        return True
    if candidate == "paper corpus":
        return False
    return len(candidate) > len(current)


def summary_to_dict(summary: SummaryChunk) -> dict[str, Any]:
    return asdict(summary)


def summary_from_dict(data: dict[str, Any]) -> SummaryChunk:
    return SummaryChunk(
        domain=str(data.get("domain") or "paper corpus"),
        purpose=str(data.get("purpose") or "Help write, revise, and review academic text."),
        terminology_preferred=_string_list(data.get("terminology_preferred")),
        terminology_avoid=_string_list(data.get("terminology_avoid")),
        section_logic=_section_map(data.get("section_logic")),
        section_expressions=_section_map(data.get("section_expressions")),
        concept_threads=_concept_threads(data.get("concept_threads")),
        writing_patterns=_string_list(data.get("writing_patterns")),
        rewrite_rules=[
            RewriteRule(
                name=str(item.get("name") or "Rewrite rule"),
                less_preferred=_string_list(item.get("less_preferred")),
                preferred=_string_list(item.get("preferred")),
            )
            for item in data.get("rewrite_rules", [])
            if isinstance(item, dict)
        ],
        ai_taste_checklist=_string_list(data.get("ai_taste_checklist")),
        examples=_string_list(data.get("examples")),
    )


def save_summary(path: Path, summary: SummaryChunk) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_summary(path: Path) -> SummaryChunk:
    return summary_from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, state: SkillState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _section_map(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _string_list(items) for key, items in value.items()}


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
                section_roles=_section_map(item.get("section_roles")),
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
