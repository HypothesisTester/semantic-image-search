# One image for both services; APP picks which one a container runs.
#
# Layers are ordered from least to most often changed, so editing the code
# only re-runs the last few, fast steps: dependencies and the model weights
# stay cached.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

WORKDIR /app

# CPU-only PyTorch. The default PyPI build for x86-64 Linux bundles CUDA
# libraries worth several GB that a CPU-only container never uses.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# The other dependencies, from pyproject.toml alone: empty package folders
# stand in for the code, which is copied later.
COPY pyproject.toml ./
RUN mkdir -p common bench demo services \
    && pip install ".[service,model]" \
    && pip uninstall -y semantic-image-search-backend

# Bake the CLIP weights (~350 MB) into the image, so a container starts
# without downloading anything, then forbid downloads at runtime. The model
# name must match common/clip.py.
RUN python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32-quickgelu', pretrained='openai')" \
    && chmod -R a+rX /opt/hf
ENV HF_HUB_OFFLINE=1

# The code. Changes here rebuild only from this point.
COPY common ./common
COPY services ./services
COPY bench ./bench
COPY demo ./demo
RUN pip install --no-deps .

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
