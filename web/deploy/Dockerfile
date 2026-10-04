# Plimsoll production runtime image.
#
# Build context is an extracted release archive (repo root of the release), never a
# working checkout, so the context contains only tools/plimsoll, web/backend,
# web/frontend/dist and web/deploy:
#
#   docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml build
#
# The same image is shared by the migrate, api and worker services.
FROM python:3.12-slim

ENV PYTHONPATH=/app/tools \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin plimsoll

# 1) production-locked third-party runtime, 2) build backend, 3) this repo's package.
COPY web/deploy/requirements-runtime.txt web/deploy/requirements-build.txt /tmp/plimsoll-requirements/
RUN pip install --no-cache-dir -r /tmp/plimsoll-requirements/requirements-runtime.txt \
 && pip install --no-cache-dir -r /tmp/plimsoll-requirements/requirements-build.txt

# Calculation core (incl. cases/ and project templates) and the FastAPI service.
COPY tools/plimsoll /app/tools/plimsoll
COPY web/backend /app/web/backend

# --no-deps keeps the runtime list above authoritative; alembic.ini/env.py and the
# alembic/versions tree ship with the package.
RUN pip install --no-cache-dir --no-build-isolation --no-deps ./web/backend \
 && rm -rf /tmp/plimsoll-requirements /app/web/backend/.pytest_cache \
 && find /app -name '__pycache__' -type d -prune -exec rm -rf {} + \
 && find /app -name '*.egg-info' -type d -prune -exec rm -rf {} +

USER plimsoll

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"]

CMD ["uvicorn", "plimsoll_web.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
