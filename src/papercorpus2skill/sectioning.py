from __future__ import annotations

import re
from dataclasses import dataclass

from papercorpus2skill.parsers import ParsedDocument


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract",),
    "introduction": ("introduction", "intro"),
    "related_work": ("related work", "background", "literature review"),
    "method": ("method", "methods", "methodology", "materials and methods", "approach", "proposed method"),
    "experiments": ("experiment", "experiments", "experimental setup", "results", "evaluation"),
    "discussion": ("discussion", "analysis"),
    "conclusion": ("conclusion", "conclusions"),
}

REFERENCE_HEADINGS = (
    "references",
    "bibliography",
    "literature cited",
    "works cited",
    "acknowledgements",
    "acknowledgments",
)


@dataclass(frozen=True)
class SectionCorpus:
    document_count: int
    sections: dict[str, list[str]]


def strip_references(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = _normalize_heading(line)
        if heading in REFERENCE_HEADINGS:
            return "\n".join(lines[:index]).strip()
    return text.strip()


def build_section_corpus(
    documents: list[ParsedDocument],
    max_documents: int = 100,
    max_chars_per_section_per_doc: int = 1800,
) -> SectionCorpus:
    sections: dict[str, list[str]] = {key: [] for key in SECTION_ALIASES}
    for document in documents[:max_documents]:
        clean_text = strip_references(document.text)
        for section, body in split_sections(clean_text).items():
            snippet = _squash(body)[:max_chars_per_section_per_doc].strip()
            if snippet:
                sections.setdefault(section, []).append(snippet)

    return SectionCorpus(
        document_count=min(len(documents), max_documents),
        sections={section: values for section, values in sections.items() if values},
    )


def split_sections(text: str) -> dict[str, str]:
    lines = strip_references(text).splitlines()
    sections: dict[str, list[str]] = {}
    current = "body"

    for line in lines:
        section = _canonical_section(line)
        if section:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return {section: "\n".join(lines).strip() for section, lines in sections.items() if section != "body" and "\n".join(lines).strip()}


def _canonical_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    for canonical, aliases in SECTION_ALIASES.items():
        if heading in aliases:
            return canonical
    return None


def _normalize_heading(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^#+\s*", "", stripped)
    stripped = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", stripped)
    stripped = stripped.strip(" :.-").lower()
    return stripped


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
