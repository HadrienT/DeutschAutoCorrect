# Single image: built SPA + API + real engines (faster-whisper, wav2vec2, espeak-ng).
FROM node:20-slim AS front
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg espeak-ng \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
# cu126 wheels still support older GPUs (Maxwell/Pascal/Volta); override for another CUDA build.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126
RUN pip install --no-cache-dir torch --index-url ${TORCH_INDEX_URL}
COPY backend/pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install --no-cache-dir -e ".[asr,pron]"
COPY backend/app ./app
COPY --from=front /src/dist /app/frontend/dist
# CTranslate2 (faster-whisper) loads cuBLAS/cuDNN from the wheels torch pulled in.
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib \
    HOME=/tmp \
    HF_HOME=/cache/huggingface \
    DAC_DATA_DIR=/data \
    PYTHONUNBUFFERED=1
EXPOSE 8010
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host ${DAC_BIND:-127.0.0.1} --port ${DAC_API_PORT:-8010}"]
