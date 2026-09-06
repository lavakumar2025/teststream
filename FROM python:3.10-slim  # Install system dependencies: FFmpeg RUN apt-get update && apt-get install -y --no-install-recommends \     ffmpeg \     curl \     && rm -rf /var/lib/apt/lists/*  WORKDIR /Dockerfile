FROM python:3.10-slim

# Install system dependencies: FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
RUN pip install --no-cache-dir pycryptodome requests streamlink

COPY main.py .

CMD ["python", "main.py"]
