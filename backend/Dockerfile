# One image for both services; APP picks which one a container runs.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

WORKDIR /app

# CPU-only PyTorch. The default PyPI build for x86-64 Linux bundles CUDA
# libraries worth several GB that a CPU-only container never uses.
# Installed first and on its own so this slow layer stays cached when the
# code changes.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml ./
COPY common ./common
COPY services ./services
COPY bench ./bench
COPY demo ./demo
RUN pip install ".[service,model]"

# Bake the CLIP weights (~350 MB) into the image, so a container starts
# without downloading anything, then forbid downloads at runtime.
RUN python -c "import common; from common.clip import ClipEncoder; ClipEncoder(device='cpu')" \
    && chmod -R a+rX /opt/hf
ENV HF_HUB_OFFLINE=1

# Run as an unprivileged user. /data becomes the named volume and inherits
# this ownership when Docker first creates it.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data /demo \
    && chown app:app /data
USER app

ENV APP=services.search \
    PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/healthz', timeout=4)"

# --proxy-headers: behind a proxy (e.g. Hugging Face Spaces), build photo
# links from the public https address rather than the internal one.
CMD ["sh", "-c", "exec uvicorn \"$APP:create_app\" --factory --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]
