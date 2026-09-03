from remote_lessons_gpt.config import settings

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "extractor_lessons_gpt.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,
    )
