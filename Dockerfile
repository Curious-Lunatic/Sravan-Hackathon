# ── Stage: runtime ──────────────────────────────────────
FROM python:3.11-slim

# System deps (for audio libs if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY heritage-storytelling-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY heritage-storytelling-agent/ ./

# Create runtime directories
RUN mkdir -p data/uploads data/audio

# Cloud platforms inject PORT; default to 8000 locally
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
