FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    PADDLE_PDX_CACHE_HOME=/tmp/paddlex

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir /wheels/* \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/models/ocr /app/models/language /home/app /tmp/paddlex \
    && chown app:app /home/app /tmp/paddlex

COPY alembic.ini .
COPY pytest.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
