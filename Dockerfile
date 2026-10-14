FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 CCP_LOG_DIR=/app/logs
WORKDIR /app

COPY requirements.txt requirements-optional.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-optional.txt

COPY ccp ./ccp
COPY config ./config
COPY contracts ./contracts
COPY data/corpus ./data/corpus
COPY eval ./eval
COPY governance ./governance
COPY prompts ./prompts

RUN useradd --create-home --uid 10001 app && mkdir -p /app/logs && chown -R app /app/logs
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/health')"
CMD ["sh", "-c", "uvicorn ccp.api:app --host 0.0.0.0 --port ${PORT}"]
