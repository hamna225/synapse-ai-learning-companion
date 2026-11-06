FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

COPY . /app

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chmod 777 /data

ENV HF_HOME=/data/huggingface \
    SYNAPSE_RESUME_DB_PATH=/data/resume_analyzer.sqlite3 \
    SYNAPSE_RESUME_FILES_PATH=/data/resumes \
    SYNAPSE_UPLOAD_DB_PATH=/data/upload_limits.sqlite3 \
    SYNAPSE_MATERIALS_PATH=/data/uploaded_materials \
    SYNAPSE_CHROMA_DB_PATH=/data/chroma_db \
    SYNAPSE_LEARNER_PROFILE_PATH=/data/learner_state.json

USER 1000
EXPOSE 7860

CMD ["sh", "-c", "if [ -z \"${SYNAPSE_API_TOKEN:-}\" ]; then echo 'Set SYNAPSE_API_TOKEN in Space Settings before starting the API.' >&2; exit 1; fi; exec uvicorn main:app --host 0.0.0.0 --port 7860"]
