FROM ghcr.io/astral-sh/uv:0.13.8 AS uv
FROM python:3.13-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN uv pip install --no-cache -r /tmp/backend-requirements.txt
# Bundle the existing Whisper model so the ECS task can start without reaching Hugging Face.
RUN python -c "from faster_whisper.utils import download_model; download_model('base')" \
    && chmod -R a+rX "$HF_HOME"
ENV HF_HUB_OFFLINE=1

COPY backend /app/backend
WORKDIR /app/backend
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "35"]
