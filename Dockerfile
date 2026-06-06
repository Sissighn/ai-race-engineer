FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    AI_RACE_ENGINEER_ROOT=/app \
    AI_RACE_ENGINEER_CACHE_DIR=/app/cache \
    AI_RACE_ENGINEER_DATA_DIR=/app/data \
    AI_RACE_ENGINEER_LOGS_DIR=/app/logs \
    AI_RACE_ENGINEER_ASSETS_DIR=/app/app/assets \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    FASTF1_CACHE_ENABLED=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements-docker.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-docker.txt

COPY app ./app
COPY src ./src

RUN mkdir -p cache data logs \
    && chown -R app:app /app

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

CMD ["streamlit", "run", "app/main.py"]
