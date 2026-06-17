FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && ln -sf /usr/bin/pip3.11 /usr/bin/pip

WORKDIR /workspace

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# app/ files land at /workspace/app/ so imports like "import layer1" resolve correctly
# when uvicorn is invoked from /workspace/app as its working directory.
COPY app/ ./app/
COPY model/ ./model/

# Hugging Face model cache — mount a persistent volume here to avoid
# re-downloading Qwen3-4B-Instruct (~2.5 GB) on every container restart:
#   docker run -v qwen_cache:/workspace/model/hf_cache ...
ENV HF_HOME=/workspace/model/hf_cache
ENV TRANSFORMERS_CACHE=/workspace/model/hf_cache

EXPOSE 8000

# Run uvicorn from app/ so that bare "import layer1" / "import llm" resolve correctly.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/workspace/app"]
