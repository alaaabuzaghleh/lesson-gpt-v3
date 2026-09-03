#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import typer

from pdf_codex_extractor.config import settings  # noqa: F401 - adds ai_book_ingestor_v4 to sys.path
from book_ingestor.schemas import BookMetadata

from pdf_codex_extractor.extract import extract_pdf

app = typer.Typer(add_completion=False, help="Extract PDF pages and index to OpenSearch")


@app.command()
def run(
    pdf: Path = typer.Argument(..., exists=True, dir_okay=False, help="Path to the PDF file"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Output directory root"),
    start_page: int = typer.Option(1, min=1, help="First page to extract (1-based)"),
    end_page: int | None = typer.Option(None, min=1, help="Last page to extract (inclusive)"),
    backend: str = typer.Option(
        settings.extractor_backend,
        "--backend",
        "-b",
        help="Extractor backend: local (Ollama VLM) or codex (ChatGPT.app)",
    ),
    language_hint: str = typer.Option(
        "Arabic mathematics textbook content",
        help="Hint passed to the extractor about expected languages",
    ),
    index: bool = typer.Option(True, "--index/--no-index", help="Index extracted pages to OpenSearch"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Skip pages already extracted in output dir"),
    title: str | None = typer.Option(None, help="Book title override"),
    subject: str | None = typer.Option(None, help="Subject override"),
    grade: str | None = typer.Option(None, help="Grade override"),
    semester: str | None = typer.Option(None, help="Semester override"),
):
    """Render PDF pages to images, extract structured text, and index to OpenSearch."""
    metadata = BookMetadata.model_validate(
        {
            k: v
            for k, v in {
                "title": title or pdf.stem.replace("-", " "),
                "subject": subject or "Mathematics",
                "grade": grade or "2",
                "semester": semester or "1",
                "country": "Saudi Arabia",
                "education_system": "National",
                "language": "ar",
            }.items()
        }
    )
    job_dir = extract_pdf(
        pdf,
        output_dir=output_dir or settings.output_dir,
        start_page=start_page,
        end_page=end_page,
        language_hint=language_hint,
        index_to_opensearch=index,
        book_metadata=metadata,
        resume=resume,
        backend=backend,
    )
    typer.echo(f"Done. Output: {job_dir}")


@app.command()
def doctor(
    backend: str = typer.Option(settings.extractor_backend, "--backend", "-b"),
):
    """Verify extractor backend, schema, and OpenSearch connectivity."""
    from pdf_codex_extractor.opensearch_indexer import OpenSearchIndexer
    from pdf_codex_extractor.runner_factory import make_page_runner

    make_page_runner(settings, backend)
    typer.echo(f"Backend: {backend}")
    if backend == "codex":
        typer.echo(f"Codex binary: {settings.codex_bin}")
    else:
        typer.echo(f"VLM: {settings.vlm_model} @ {settings.vlm_base_url}")
    typer.echo(f"Schema: {settings.page_schema}")
    if settings.index_to_opensearch:
        OpenSearchIndexer(settings)
        typer.echo(f"OpenSearch: {settings.opensearch_url} index={settings.opensearch_index}")
    typer.echo("OK")


if __name__ == "__main__":
    app()
