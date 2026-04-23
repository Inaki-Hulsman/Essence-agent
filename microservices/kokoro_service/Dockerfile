FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    kokoro-onnx \
    numpy \
    soundfile \
    pydantic

COPY main.py .

# Los modelos se montan como volumen (ver docker-compose)
ENV KOKORO_MODEL_PATH=/models/kokoro-v1.0.onnx
ENV KOKORO_VOICES_PATH=/models/voices-v1.0.bin
ENV KOKORO_VOICE=ef_dora
ENV KOKORO_LANG=es

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]