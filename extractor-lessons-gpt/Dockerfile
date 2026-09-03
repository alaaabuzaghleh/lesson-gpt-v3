FROM python:3.12-slim

WORKDIR /app

COPY extractor-lessons-gpt/requirements.txt /app/extractor-lessons-gpt/requirements.txt
RUN pip install --no-cache-dir -r /app/extractor-lessons-gpt/requirements.txt

COPY remote-lessons-gpt/remote_lessons_gpt /app/remote_lessons_gpt
COPY extractor-lessons-gpt /app/extractor-lessons-gpt

ENV PYTHONPATH=/app:/app/extractor-lessons-gpt

WORKDIR /app/extractor-lessons-gpt
EXPOSE 8080
CMD ["python", "run_api.py"]
