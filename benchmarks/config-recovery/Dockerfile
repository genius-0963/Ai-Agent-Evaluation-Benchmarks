FROM python:3.12-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

# Create an unprivileged user and workspace
RUN useradd -m -u 1000 -s /bin/bash benchuser && \
    mkdir -p /workspace && \
    chown -R benchuser:benchuser /workspace

WORKDIR /workspace

# Install pinned dependencies
RUN pip install --no-cache-dir \
    "fastapi==0.115.0" \
    "uvicorn==0.30.6" \
    "pydantic-settings==2.5.2" \
    "httpx==0.27.2" \
    "pytest==8.3.3"

# Copy sample application
COPY --chown=benchuser:benchuser app/ /workspace/app/

# Introduce the controlled fault by copying broken .env
COPY --chown=benchuser:benchuser fixtures/broken.env /workspace/.env

# Switch to non-root user
USER benchuser

EXPOSE 8000

# Default command: start server via python uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
