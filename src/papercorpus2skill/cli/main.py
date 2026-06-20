from __future__ import annotations

import argparse
import sys
from pathlib import Path

from papercorpus2skill.agent import PaperCorpus2SkillAgent
from papercorpus2skill.batch import BatchPaperCorpus2SkillAgent, discover_corpus_groups
from papercorpus2skill.config import AppConfig, load_config
from papercorpus2skill.corpus import discover_sources
from papercorpus2skill.env import load_dotenv
from papercorpus2skill.llm import LLMConfig, ProviderConfigurationError, create_provider


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(prog="papercorpus2skill")
    parser.add_argument("--config", default="papercorpus2skill.yaml", help="Path to config file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview_parser = subparsers.add_parser("preview", help="Preview supported corpus files.")
    preview_parser.add_argument("input_path")
    preview_parser.add_argument("--zotero", action="store_true", help="Treat the input as a local Zotero data/storage folder.")

    batch_preview_parser = subparsers.add_parser("batch-preview", help="Preview one-corpus-per-subfolder batch input.")
    batch_preview_parser.add_argument("input_root")

    doctor_parser = subparsers.add_parser("doctor", help="Check local environment.")
    doctor_parser.add_argument("--provider", default=None)
    doctor_parser.add_argument("--model", default=None)

    generate_parser = subparsers.add_parser("generate", help="Generate a Skill Pack from a corpus.")
    generate_parser.add_argument("input_path")
    generate_parser.add_argument("--output-dir", default=None)
    generate_parser.add_argument("--type", default=None, dest="skill_type")
    generate_parser.add_argument("--export", default=None)
    generate_parser.add_argument("--provider", default=None)
    generate_parser.add_argument("--base-url", default=None)
    generate_parser.add_argument("--model", default=None)
    generate_parser.add_argument("--api-key", default=None)
    generate_parser.add_argument("--api-key-env", default=None)
    generate_parser.add_argument("--temperature", type=float, default=0.2)
    generate_parser.add_argument("--zotero", action="store_true", help="Scan local Zotero storage recursively.")
    generate_parser.add_argument("--no-zip", action="store_true")

    batch_parser = subparsers.add_parser("batch", help="Generate one Skill Pack per top-level corpus folder.")
    batch_parser.add_argument("input_root")
    batch_parser.add_argument("--output-dir", default=None)
    batch_parser.add_argument("--type", default=None, dest="skill_type")
    batch_parser.add_argument("--export", default=None)
    batch_parser.add_argument("--provider", default=None)
    batch_parser.add_argument("--base-url", default=None)
    batch_parser.add_argument("--model", default=None)
    batch_parser.add_argument("--api-key", default=None)
    batch_parser.add_argument("--api-key-env", default=None)
    batch_parser.add_argument("--temperature", type=float, default=0.2)
    batch_parser.add_argument("--no-zip", action="store_true")

    args = parser.parse_args(argv)
    config = load_config(Path(args.config))
    if args.command == "preview":
        return _preview(Path(args.input_path), include_zotero=args.zotero)
    if args.command == "batch-preview":
        return _batch_preview(Path(args.input_root))
    if args.command == "doctor":
        return _doctor(provider=args.provider, model=args.model)
    if args.command == "generate":
        return _generate(args, config)
    if args.command == "batch":
        return _batch(args, config)
    raise AssertionError(f"Unhandled command: {args.command}")


def _preview(input_path: Path, include_zotero: bool) -> int:
    sources = discover_sources(input_path, include_zotero=include_zotero)
    pdf_count = sum(1 for source in sources if source.kind == "pdf")
    markdown_count = sum(1 for source in sources if source.kind == "markdown")
    print("Corpus Preview")
    print()
    print(f"Files detected: {len(sources)}")
    print(f"PDF files: {pdf_count}")
    print(f"Markdown files: {markdown_count}")
    if include_zotero:
        print("Zotero mode: local storage scan")
    return 0


def _batch_preview(input_root: Path) -> int:
    groups = discover_corpus_groups(input_root)
    print("Batch Corpus Preview")
    print()
    print(f"Corpus groups detected: {len(groups)}")
    for group in groups:
        print(f"- {group.name}: {group.source_count} files")
    return 0


def _doctor(provider: str | None, model: str | None) -> int:
    print("PaperCorpus2Skill Environment Check")
    print()
    print(f"Python: {sys.version.split()[0]}")
    try:
        import fitz  # type: ignore[import-not-found]

        print(f"PyMuPDF: OK ({fitz.__doc__.splitlines()[0] if fitz.__doc__ else 'installed'})")
    except ImportError:
        print("PyMuPDF: Not installed (PDF parsing will require `uv add PyMuPDF`)")
    print(f"LLM provider: {provider or 'not configured'}")
    print(f"LLM model: {model or 'not configured'}")
    return 0


def _generate(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        target_tools = _target_tools(args.export, config)
        llm_config = _llm_config(args, config)
        provider = create_provider(llm_config)
        pack = PaperCorpus2SkillAgent(provider).generate(
            input_path=Path(args.input_path),
            output_dir=Path(args.output_dir) if args.output_dir else config.app.output_dir,
            skill_type=args.skill_type or config.generation.skill_type,
            target_tools=target_tools,
            include_zotero=args.zotero,
            create_zip=False if args.no_zip else config.generation.create_zip,
            cache_dir=config.app.cache_dir,
            papers_per_batch=config.processing.papers_per_batch,
            summaries_per_merge=config.processing.summaries_per_merge,
            pdf_backend=config.processing.pdf_backend,
        )
    except (RuntimeError, FileNotFoundError, ProviderConfigurationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Your Skill Pack is ready.")
    print(f"Output: {pack.root}")
    zip_path = pack.root.with_suffix(".zip")
    if zip_path.exists():
        print(f"ZIP: {zip_path}")
    return 0


def _batch(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        target_tools = _target_tools(args.export, config)
        llm_config = _llm_config(args, config)
        provider = create_provider(llm_config)
        result = BatchPaperCorpus2SkillAgent(provider).generate_all(
            input_root=Path(args.input_root),
            output_dir=Path(args.output_dir) if args.output_dir else config.app.output_dir,
            skill_type=args.skill_type or config.generation.skill_type,
            target_tools=target_tools,
            create_zip=False if args.no_zip else config.generation.create_zip,
            cache_dir=config.app.cache_dir,
            papers_per_batch=config.processing.papers_per_batch,
            summaries_per_merge=config.processing.summaries_per_merge,
            pdf_backend=config.processing.pdf_backend,
        )
    except (RuntimeError, FileNotFoundError, ProviderConfigurationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Batch Skill Packs are ready.")
    for item in result.items:
        print(f"- {item.group.name}: {item.pack.root}")
    return 0


def _target_tools(export_arg: str | None, config: AppConfig) -> list[str]:
    if export_arg:
        return [target.strip() for target in export_arg.split(",") if target.strip()]
    return config.generation.target_tools


def _llm_config(args: argparse.Namespace, config: AppConfig) -> LLMConfig:
    model = args.model or config.llm.model
    if not model:
        raise ProviderConfigurationError(
            "No LLM model configured. Set llm.model in papercorpus2skill.yaml or pass --model."
        )
    return LLMConfig(
        provider=args.provider or config.llm.provider,
        base_url=args.base_url or config.llm.base_url,
        model=model,
        api_key=args.api_key,
        api_key_env=args.api_key_env or config.llm.api_key_env,
        temperature=args.temperature if args.temperature != 0.2 else config.llm.temperature,
    )


if __name__ == "__main__":
    raise SystemExit(main())
