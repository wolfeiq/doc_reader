
# Build: docker build -t doc-reader-backend .
# Run:   docker run -p 8000:8000 --env-file .env doc-reader-backend

FROM python:3.11-slim as builder

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*


COPY pyproject.toml ./
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir .


FROM python:3.11-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*


COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin


COPY . .
RUN chmod +x start.sh


RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser


EXPOSE 8000


HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1


CMD ["./start.sh"]
