# PaperCorpus2Skill Agent MVP Design

## Goal

Build the first local agent for PaperCorpus2Skill: a Python CLI and reusable core pipeline that turns a folder of PDF and Markdown papers into a portable Markdown Skill Pack.

## Scope

The first version supports:
- Recursive folder input.
- Direct PDF and Markdown file input.
- Zotero local storage folders, including PDFs synced from Zotero WebDAV when the PDF exists on disk.
- OpenAI-compatible, Anthropic-style, Ollama, and test/mock LLM providers through one interface.
- Skill Pack rendering for universal Markdown, Claude, ChatGPT, Codex, and Cursor exports.

The first version does not directly authenticate to remote WebDAV. If Zotero has not downloaded the PDF locally, the user must sync/download it first.

## Architecture

The implementation is a small Python package under `src/papercorpus2skill`. The `PaperCorpus2SkillAgent` owns the main workflow and delegates to focused modules:
- `corpus.py` discovers supported source files.
- `parsers.py` extracts text from Markdown and PDF.
- `llm.py` normalizes provider calls.
- `analyzers.py` asks the LLM for structured corpus guidance.
- `skills.py` renders the Skill Pack and export files.
- `cli/main.py` exposes `generate`, `preview`, and `doctor`.

The CLI and any later Web UI will call the same agent instead of duplicating logic.

## Data Flow

1. Discover PDF and Markdown files from the requested path.
2. Parse each file into `ParsedDocument`.
3. Build a compact corpus prompt with document titles and truncated text.
4. Ask the configured LLM provider for JSON guidance.
5. Render the guidance into a Skill Pack directory.
6. Optionally create a zip archive.

## Error Handling

The agent fails fast when no supported files are found or when no usable LLM provider is configured. PDF parsing requires PyMuPDF; if it is missing, PDF parsing reports a clear dependency error. Markdown parsing uses plain UTF-8 text loading and does not require external dependencies.

## Testing

Tests cover file discovery, Zotero-style recursive PDF discovery, Markdown parsing, agent orchestration with a fake provider, skill export paths, and CLI smoke behavior.
