FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# app/ files land at /workspace/app/ so bare imports like "import layer1" resolve correctly
COPY app/ ./app/
COPY model/ ./model/

EXPOSE 8000

# GROQ_API_KEY and GROQ_MODEL must be set as environment variables at runtime
# Example: docker run -e GROQ_API_KEY=gsk_... -e GROQ_MODEL=qwen-qwen3-32b ...
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/workspace/app"]
