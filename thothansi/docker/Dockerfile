# Thothansi — AI-assisted passive recon & triage
FROM python:3.12-slim

# Non-root user for safety.
RUN useradd --create-home --shell /bin/bash thoth

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY thothansi ./thothansi
RUN pip install --no-cache-dir . && \
    mkdir -p /app/config /app/thothansi-data && \
    chown -R thoth:thoth /app

USER thoth

# Default data dir lives on a volume (see docker-compose).
ENV THOTHANSI_PROVIDER=ollama

EXPOSE 8000

# Default: launch the web dashboard. Override the command for CLI use, e.g.:
#   docker run --rm -it thothansi thothansi run example.com
ENTRYPOINT ["thothansi"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
