FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
# MinerU models are large; run mineru-api separately and set MINERU_API_URL.

COPY . .
RUN mkdir -p /app/data

EXPOSE 8080
CMD ["python", "run_api.py"]
