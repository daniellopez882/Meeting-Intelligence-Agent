FROM python:3.12-slim AS build

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app src/ ./src/
COPY --chown=app:app public/ ./public/

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIND_HOST=0.0.0.0 \
    PORT=8000

USER app
EXPOSE 8000

# Startup validates a production configuration and refuses to serve on the
# placeholder API key, so a container that is up has passed that check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["sh", "-c", "uvicorn src.api:app --host ${BIND_HOST} --port ${PORT}"]
