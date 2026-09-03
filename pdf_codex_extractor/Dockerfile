FROM python:3.12-slim

WORKDIR /app

COPY pdf_codex_extractor/requirements.txt /app/pdf_codex_extractor/requirements.txt
RUN pip install --no-cache-dir -r /app/pdf_codex_extractor/requirements.txt

COPY ai_book_ingestor_v4/book_ingestor /app/book_ingestor
COPY pdf_codex_extractor /app/pdf_codex_extractor

ENV PYTHONPATH=/app:/app/pdf_codex_extractor

WORKDIR /app/pdf_codex_extractor
EXPOSE 8080
CMD ["python", "run_api.py"]
