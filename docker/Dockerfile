FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    postgresql-client \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Upgrade pip only — keep setuptools pinned in requirements
RUN pip install --upgrade pip
# Install all dependencies (faster-whisper has pre-built wheels — no compilation)
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download faster-whisper base model (cached in image layer — no network at runtime)
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

# Pre-download sentence-transformers embedding model (cached in image layer)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

# Make entrypoint executable
RUN chmod +x docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
