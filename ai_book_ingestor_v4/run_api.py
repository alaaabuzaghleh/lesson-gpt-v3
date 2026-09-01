from book_ingestor.config import settings

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "book_ingestor.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,
    )
