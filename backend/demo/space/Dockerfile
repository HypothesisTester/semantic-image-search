# Hugging Face Space image for the public demo: the search service in demo
# mode, with the COCO index and thumbnails built in. demo/deploy_space.py
# copies this file to the Space as its Dockerfile, next to the backend code
# and a demo-data/ folder.
#
# Same layer order as backend/Dockerfile, so code-only updates rebuild fast.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

WORKDIR /app

RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml ./
RUN mkdir -p common bench demo services \
    && pip install ".[service,model]" \
    && pip uninstall -y semantic-image-search-backend

# The model name must match common/clip.py.
RUN python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32-quickgelu', pretrained='openai')" \
    && chmod -R a+rX /opt/hf
ENV HF_HUB_OFFLINE=1

# The demo's index and thumbnails. The thumbnails arrive as one tar file:
# a single 120 MB upload instead of 5,000 small ones.
COPY demo-data/index /demo/index
COPY demo-data/thumbnails.tar /tmp/thumbnails.tar
RUN mkdir -p /demo/thumbnails \
    && tar -xf /tmp/thumbnails.tar -C /demo/thumbnails \
    && rm /tmp/thumbnails.tar \
    && chmod -R a+rX /demo

COPY common ./common
COPY services ./services
COPY bench ./bench
COPY demo ./demo
RUN pip install --no-deps .

# Spaces run containers as user id 1000.
RUN useradd --create-home --uid 1000 user
USER user

# CORS_ORIGINS=*: the demo is public, read-only and uses no cookies or
# tokens, so any site may call it. (The signed-in services list their
# frontend's address instead.) PHOTOS_BASE_URL is set as a Space variable
# by the deploy script, so photo links use the Space's public address.
ENV APP=services.search \
    PORT=7860 \
    DEMO_MODE=1 \
    DEMO_DIR=/demo \
    CORS_ORIGINS=*
EXPOSE 7860

CMD ["sh", "-c", "exec uvicorn \"$APP:create_app\" --factory --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]
