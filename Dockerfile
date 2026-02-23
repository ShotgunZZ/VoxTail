# Speaker Recognition PWA - Production Dockerfile
FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install CPU-only PyTorch first (much smaller than CUDA version - ~200MB vs 2-3GB)
RUN pip install --no-cache-dir \
    torch==2.1.2 \
    torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cpu

# Install other Python dependencies
RUN pip install --no-cache-dir \
    "numpy<2" \
    speechbrain \
    soundfile \
    pinecone \
    assemblyai \
    pydub \
    python-dotenv \
    silero-vad \
    scipy \
    fastapi \
    uvicorn[standard] \
    python-multipart \
    huggingface_hub==0.23.5 \
    openai \
    google-api-python-client \
    google-auth

# Copy application code
COPY . .

# Create temp directory (will be cleaned on startup anyway)
RUN mkdir -p meeting_audio_temp

# Pre-download SpeechBrain model to cache it in Docker image
# This avoids memory spikes from downloading during inference
RUN python -c "from speechbrain.inference.speaker import EncoderClassifier; \
    EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', \
    savedir='pretrained_models/spkrec-ecapa-voxceleb', run_opts={'device': 'cpu'})"

# Expose port (Railway uses PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Start command - use PORT env var from Railway
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
