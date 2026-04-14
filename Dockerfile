FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system juridico && useradd --system --gid juridico juridico

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --chown=juridico:juridico . .

RUN mkdir -p /data /app/storage/uploads /app/storage/generations \
    && chown -R juridico:juridico /data /app/storage

USER juridico

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
