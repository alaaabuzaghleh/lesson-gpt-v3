from book_ingestor.config import settings

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "pdf_codex_extractor.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,
    )
