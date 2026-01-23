FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml AND README.md (required by Hatchling) first
COPY pyproject.toml README.md ./

# Install your package in editable mode
RUN pip install --no-cache-dir -e .

# Copy the rest of your source code
COPY . .

# Expose port
EXPOSE 8080

# Start the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
