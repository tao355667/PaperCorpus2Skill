from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from papercorpus2skill.analyzers import CorpusGuidance


@dataclass(frozen=True)
class SkillPack:
    name: str
    root: Path
    files: list[Path]

    def zip(self) -> Path:
        zip_path = self.root.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in self.files:
                archive.write(path, path.relative_to(self.root))
        return zip_path


def render_skill_pack(
    guidance: CorpusGuidance,
    output_dir: Path,
    skill_type: str,
    source_file_count: int,
    target_tools: list[str],
) -> SkillPack:
    name = f"{_slugify(guidance.domain)}-{skill_type.replace('_', '-')}-skill"
    root = output_dir / name
    files_dir = root / "files"
    exports_dir = root / "exports"
    files_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    written.append(_write(root / "SKILL.md", _skill_md(guidance, name)))
    written.append(_write(files_dir / "phrasebook.md", _phrasebook(guidance)))
    written.append(_write(files_dir / "section-logic.md", _section_logic(guidance)))
    written.append(_write(files_dir / "section-expressions.md", _section_expressions(guidance)))
    written.append(_write(files_dir / "concept-threads.md", _concept_threads(guidance)))
    written.append(_write(files_dir / "paper-level-patterns.md", _paper_level_patterns(guidance)))
    written.append(_write(files_dir / "writing-patterns.md", _list_doc("Writing Patterns", guidance.writing_patterns)))
    written.append(_write(files_dir / "rewrite-rules.md", _rewrite_rules(guidance)))
    written.append(_write(files_dir / "ai-taste-checklist.md", _list_doc("AI Taste Checklist", guidance.ai_taste_checklist)))
    written.append(_write(files_dir / "examples.md", _list_doc("Examples", guidance.examples)))
    written.append(
        _write(
            root / "skill.json",
            json.dumps(
                {
                    "name": name,
                    "project": "PaperCorpus2Skill",
                    "skill_type": skill_type,
                    "domain": guidance.domain,
                    "source_file_count": source_file_count,
                    "generated_files": [path.name for path in written],
                    "export_targets": target_tools,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )
    )

    if "universal" in target_tools:
        universal = exports_dir / "universal"
        universal.mkdir(parents=True, exist_ok=True)
        written.append(_write(universal / "SKILL.md", _skill_md(guidance, name)))
    if "claude" in target_tools:
        claude = exports_dir / "claude"
        claude.mkdir(parents=True, exist_ok=True)
        written.append(_write(claude / "SKILL.md", _skill_md(guidance, name)))
    if "chatgpt" in target_tools:
        chatgpt = exports_dir / "chatgpt"
        chatgpt.mkdir(parents=True, exist_ok=True)
        written.append(_write(chatgpt / "project-instructions.md", _chatgpt(guidance)))
    if "codex" in target_tools:
        codex = exports_dir / "codex"
        codex.mkdir(parents=True, exist_ok=True)
        written.append(_write(codex / "AGENTS.md", _codex(guidance)))
    if "cursor" in target_tools:
        cursor = exports_dir / "cursor"
        cursor.mkdir(parents=True, exist_ok=True)
        written.append(_write(cursor / "corpus2skill.mdc", _cursor(guidance)))

    return SkillPack(name=name, root=root, files=written)


def _skill_md(guidance: CorpusGuidance, name: str) -> str:
    return "\n".join(
        [
            f"# {guidance.domain} Academic Writing Skill",
            "",
            "## Purpose",
            "",
            guidance.purpose,
            "",
            "## When to Use",
            "",
            "- Writing or revising academic paper sections.",
            "- Checking terminology, style, and section logic.",
            "- Reducing generic AI-like expressions while preserving technical meaning.",
            "",
            "## Core Instructions",
            "",
            "- Use conservative academic claims.",
            "- Prefer domain-specific terminology over generic wording.",
            "- Preserve citations, metrics, datasets, and technical facts from the user's draft.",
            "- Do not invent experimental results or references.",
            "- Do not copy source corpus sentences verbatim.",
            "",
            "## Reference Files",
            "",
            "- `files/phrasebook.md`",
            "- `files/section-logic.md`",
            "- `files/section-expressions.md`",
            "- `files/concept-threads.md`",
            "- `files/paper-level-patterns.md`",
            "- `files/writing-patterns.md`",
            "- `files/rewrite-rules.md`",
            "- `files/ai-taste-checklist.md`",
            "- `files/examples.md`",
            "",
            f"Generated by PaperCorpus2Skill as `{name}`.",
            "",
        ]
    )


def _phrasebook(guidance: CorpusGuidance) -> str:
    return "\n".join(
        [
            "# Phrasebook",
            "",
            "## Preferred",
            "",
            *_bullets(guidance.terminology_preferred),
            "",
            "## Avoid",
            "",
            *_bullets(guidance.terminology_avoid),
            "",
        ]
    )


def _section_logic(guidance: CorpusGuidance) -> str:
    lines = ["# Section Logic", ""]
    for section, steps in guidance.section_logic.items():
        lines.extend([f"## {section}", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        lines.append("")
    return "\n".join(lines)


def _section_expressions(guidance: CorpusGuidance) -> str:
    lines = ["# Section Expressions", ""]
    for section, expressions in guidance.section_expressions.items():
        lines.extend([f"## {section.replace('_', ' ').title()}", ""])
        lines.extend(_bullets(expressions))
        lines.append("")
    if not guidance.section_expressions:
        lines.extend(_bullets([]))
        lines.append("")
    return "\n".join(lines)


def _concept_threads(guidance: CorpusGuidance) -> str:
    lines = ["# Concept Threads", ""]
    if not guidance.concept_threads:
        lines.extend(_bullets([]))
        lines.append("")
        return "\n".join(lines)

    for thread in guidance.concept_threads:
        lines.extend([f"## {thread.concept}", ""])
        if thread.aliases:
            lines.extend(["Aliases:", ""])
            lines.extend(_bullets(thread.aliases))
            lines.append("")
        role_pairs = [
            ("Problem role", thread.problem_role),
            ("Method role", thread.method_role),
            ("Evidence role", thread.evidence_role),
            ("Discussion role", thread.discussion_role),
            ("Claim strength", thread.claim_strength),
        ]
        for label, value in role_pairs:
            if value:
                lines.extend([f"{label}: {value}", ""])
        if thread.section_roles:
            non_empty_roles = {
                section: roles for section, roles in thread.section_roles.items() if roles
            }
            if non_empty_roles:
                lines.extend(["Section roles:", ""])
                for section, roles in non_empty_roles.items():
                    lines.extend([f"### {section.replace('_', ' ').title()}", ""])
                    lines.extend(_bullets(roles))
                    lines.append("")
        if thread.common_transitions:
            lines.extend(["Common transitions:", ""])
            lines.extend(_bullets(thread.common_transitions))
            lines.append("")
        if thread.do_not_confuse_with:
            lines.extend(["Do not confuse with:", ""])
            lines.extend(_bullets(thread.do_not_confuse_with))
            lines.append("")
        if thread.writing_guidance:
            lines.extend(["Writing guidance:", ""])
            lines.extend(_bullets(thread.writing_guidance))
            lines.append("")
    return "\n".join(lines)


def _paper_level_patterns(guidance: CorpusGuidance) -> str:
    lines = ["# Paper-Level Patterns", "", "## Section Structure", ""]
    for section, steps in guidance.section_logic.items():
        lines.extend([f"### {section.replace('_', ' ').title()}", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        lines.append("")
    lines.extend(["## Writing Patterns", ""])
    lines.extend(_bullets(guidance.writing_patterns))
    lines.append("")
    return "\n".join(lines)


def _rewrite_rules(guidance: CorpusGuidance) -> str:
    lines = ["# Rewrite Rules", ""]
    for rule in guidance.rewrite_rules:
        lines.extend([f"## {rule.name}", "", "Less preferred:", ""])
        lines.extend(_bullets(rule.less_preferred))
        lines.extend(["", "Preferred:", ""])
        lines.extend(_bullets(rule.preferred))
        lines.append("")
    return "\n".join(lines)


def _chatgpt(guidance: CorpusGuidance) -> str:
    return "\n".join(
        [
            f"Use this project as a {guidance.domain} academic writing assistant.",
            "",
            guidance.purpose,
            "",
            "Rules:",
            "- Preserve technical meaning, citations, metrics, and datasets.",
            "- Prefer precise domain terminology.",
            "- Avoid exaggerated claims and generic AI phrasing.",
            "- Do not invent sources or experimental results.",
            "",
            "Preferred terminology:",
            *_bullets(guidance.terminology_preferred),
            "",
        ]
    )


def _codex(guidance: CorpusGuidance) -> str:
    return "\n".join(
        [
            "# AGENTS.md",
            "",
            f"You are assisting with academic writing using a generated corpus skill for {guidance.domain}.",
            "",
            "When editing manuscript text:",
            "- Follow the domain terminology in this file.",
            "- Prefer concise academic writing.",
            "- Avoid generic AI-like expressions.",
            "- Do not invent experimental results, metrics, datasets, or citations.",
            "- Preserve technical meaning.",
            "",
            "Preferred terminology:",
            *_bullets(guidance.terminology_preferred),
            "",
        ]
    )


def _cursor(guidance: CorpusGuidance) -> str:
    return "\n".join(
        [
            "---",
            "description: PaperCorpus2Skill generated academic writing rule",
            "alwaysApply: false",
            "---",
            "",
            f"Apply these rules when editing {guidance.domain} paper text:",
            "- Preserve facts, citations, metrics, and datasets.",
            "- Use precise domain terminology.",
            "- Avoid exaggerated novelty claims.",
            "- Do not copy corpus sentences verbatim.",
            "",
        ]
    )


def _list_doc(title: str, values: list[str]) -> str:
    return "\n".join([f"# {title}", "", *_bullets(values), ""])


def _bullets(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values] or ["- No corpus-specific items were generated."]


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "paper-corpus"
