from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()

from .config import settings
from .pipeline import BookIngestionPipeline
from .search import BookSearchService

app = typer.Typer(no_args_is_help=True, help="Universal Arabic/English textbook ingestion + question intelligence + visual understanding + OpenSearch lexical search.")
console = Console()


@app.command()
def ingest(
    pdf: Path = typer.Argument(..., exists=True, readable=True, help="Input textbook PDF"),
    output: Path = typer.Option(Path("./output"), "--output", "-o"),
    country: Optional[str] = typer.Option(None),
    curriculum: Optional[str] = typer.Option(None),
    education_system: Optional[str] = typer.Option(None),
    grade: Optional[str] = typer.Option(None),
    subject: Optional[str] = typer.Option(None),
    semester: Optional[str] = typer.Option(None),
    academic_year: Optional[str] = typer.Option(None),
    language: Optional[str] = typer.Option(None),
    start_page: int = typer.Option(1, min=1),
    end_page: Optional[int] = typer.Option(None, min=1),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    index: bool = typer.Option(True, "--index/--no-index", help="Index extracted records into OpenSearch"),
    recreate_index: bool = typer.Option(False, help="Delete and recreate the OpenSearch index"),
):
    overrides = {
        "country": country,
        "curriculum": curriculum,
        "education_system": education_system,
        "grade": grade,
        "subject": subject,
        "semester": semester,
        "academic_year": academic_year,
        "language": language,
    }
    pipeline = BookIngestionPipeline(pdf, output)
    _, book_id, docs = pipeline.run(overrides, start_page, end_page, resume)

    console.print(f"[green]Book ID:[/green] {book_id}")
    console.print(f"[green]Extracted records:[/green] {len(docs)}")
    console.print(f"[green]Visual assets:[/green] {sum(1 for d in docs if d.asset_id)}")

    if index:
        from .opensearch_index import bulk_index, create_client, ensure_index

        client = create_client()
        ensure_index(client, settings.opensearch_index, recreate=recreate_index)
        success, errors = bulk_index(client, settings.opensearch_index, [d.model_dump(mode="json") for d in docs])
        console.print(f"[green]Indexed:[/green] {success}")
        if errors:
            console.print(f"[red]Bulk errors:[/red] {len(errors)}")


@app.command("create-index")
def create_index(recreate: bool = typer.Option(False)):
    from .opensearch_index import create_client, ensure_index

    client = create_client()
    ensure_index(client, settings.opensearch_index, recreate=recreate)
    console.print(f"Index ready: {settings.opensearch_index}")


@app.command()
def search(
    query: str = typer.Argument(...),
    book_id: Optional[str] = typer.Option(None),
    country: Optional[str] = typer.Option(None),
    curriculum: Optional[str] = typer.Option(None),
    grade: Optional[str] = typer.Option(None),
    subject: Optional[str] = typer.Option(None),
    content_type: Optional[str] = typer.Option(None),
    visual_type: Optional[str] = typer.Option(None),
    question_scope: Optional[str] = typer.Option(None),
    question_format: Optional[str] = typer.Option(None),
    question_purpose: Optional[str] = typer.Option(None),
    question_bloom_level: Optional[str] = typer.Option(None),
    size: int = typer.Option(15, min=1, max=100),
):
    filters = {
        k: v
        for k, v in {
            "book_id": book_id,
            "country": country.casefold() if country else None,
            "curriculum": curriculum.casefold() if curriculum else None,
            "grade": grade.casefold() if grade else None,
            "subject": subject.casefold() if subject else None,
            "content_type": content_type,
            "visual_type": visual_type,
            "question_scope": question_scope,
            "question_format": question_format,
            "question_purpose": question_purpose,
            "question_bloom_level": question_bloom_level,
        }.items()
        if v is not None
    }
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    results = service.search(query, filters, size=size)
    table = Table("score", "type", "q.scope", "q.format", "visual", "page", "lesson", "title/text")
    for r in results:
        table.add_row(
            f"{r.get('score', 0) or 0:.3f}",
            str(r.get("content_type") or ""),
            str(r.get("question_scope") or ""),
            str(r.get("question_format") or ""),
            str(r.get("visual_type") or ""),
            str(r.get("printed_page_number") or r.get("pdf_page_number") or ""),
            str(r.get("lesson_title") or "")[:30],
            str(r.get("title") or r.get("visual_summary") or r.get("text") or "")[:90].replace("\n", " "),
        )
    console.print(table)


@app.command("page")
def exact_page(book_id: str, page: str):
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    console.print_json(data=service.exact_page(book_id, page))


@app.command("question")
def find_question(book_id: str, page: str, number: str):
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    console.print_json(data=service.find_question(book_id, page, number))


@app.command("questions")
def find_questions(
    book_id: str,
    query: Optional[str] = typer.Option(None),
    scope: Optional[str] = typer.Option(None),
    question_format: Optional[str] = typer.Option(None, "--format"),
    purpose: Optional[str] = typer.Option(None),
    bloom_level: Optional[str] = typer.Option(None),
    difficulty: Optional[str] = typer.Option(None),
    lesson_title: Optional[str] = typer.Option(None),
    chapter_title: Optional[str] = typer.Option(None),
    unit_title: Optional[str] = typer.Option(None),
    requires_visual: Optional[bool] = typer.Option(None),
    size: int = typer.Option(100, min=1, max=500),
):
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    console.print_json(data=service.find_questions(
        book_id=book_id,
        query=query,
        scope=scope,
        question_format=question_format,
        purpose=purpose,
        bloom_level=bloom_level,
        difficulty=difficulty,
        lesson_title=lesson_title,
        chapter_title=chapter_title,
        unit_title=unit_title,
        requires_visual=requires_visual,
        size=size,
    ))


@app.command("question-context")
def question_context(question_id: str, radius: int = typer.Option(2, min=0, max=10)):
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    result = service.get_question_context(question_id, radius=radius)
    if result is None:
        raise typer.Exit(code=1)
    console.print_json(data=result)


@app.command("visuals")
def find_visuals(
    book_id: str,
    page: Optional[str] = typer.Option(None),
    visual_type: Optional[str] = typer.Option(None),
    query: Optional[str] = typer.Option(None),
    size: int = typer.Option(50, min=1, max=200),
):
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    console.print_json(data=service.find_visuals(book_id, page=page, visual_type=visual_type, query=query, size=size))


@app.command("asset")
def get_asset(asset_id: str):
    from .opensearch_index import create_client

    service = BookSearchService(create_client(), settings.opensearch_index)
    result = service.get_asset(asset_id)
    if result is None:
        raise typer.Exit(code=1)
    console.print_json(data=result)


if __name__ == "__main__":
    app()
