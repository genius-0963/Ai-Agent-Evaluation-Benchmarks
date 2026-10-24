FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

RUN useradd -m -u 1000 -s /bin/bash benchuser && \
    mkdir -p /workspace && \
    chown -R benchuser:benchuser /workspace

WORKDIR /workspace

RUN pip install --no-cache-dir \
    "fastapi==0.115.0" \
    "uvicorn==0.30.6" \
    "pydantic-settings==2.5.2" \
    "httpx==0.27.2" \
    "pytest==8.3.3"

COPY --chown=benchuser:benchuser app/ /workspace/app/
COPY --chown=benchuser:benchuser fixtures/broken.env /workspace/.env

USER benchuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
