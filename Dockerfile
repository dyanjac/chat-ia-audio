FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_HOST=0.0.0.0 \
    GRADIO_PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY app.py .
COPY sales_agent ./sales_agent
COPY mcp_server ./mcp_server

EXPOSE 7860

CMD ["uvicorn", "sales_agent.web:app", "--host", "0.0.0.0", "--port", "7860"]
