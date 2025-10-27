FROM python:3.11-slim

# demucs and its deps (large, but matches the README guidance)
RUN apt-get update && apt-get install -y git build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir redis minio requests demucs==4.0.1

WORKDIR /app
COPY worker-server.py .
CMD ["python", "worker-server.py"]

# ... your existing base + installs ...
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torchcodec
# ... copy code, set entrypoint, etc ...
