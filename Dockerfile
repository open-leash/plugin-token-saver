FROM python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00

LABEL org.opencontainers.image.title="OpenLeash token-saver" \
      org.opencontainers.image.source="https://github.com/open-leash/plugin-token-saver" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENLEASH_PLUGIN_DATA_DIR=/data \
    HF_HOME=/data/huggingface \
    XDG_CACHE_HOME=/data/cache \
    HEADROOM_HOME=/data/headroom

RUN addgroup --system openleash && adduser --system --ingroup openleash openleash
WORKDIR /app
COPY engine/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY engine/server.py ./server.py
RUN mkdir -p /data && chown -R openleash:openleash /app /data
USER openleash
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
