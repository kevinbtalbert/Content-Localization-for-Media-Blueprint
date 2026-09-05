# syntax=docker/dockerfile:1
# Unified Content Localization image for Cloudera AI Workbench (and optional local docker-compose).
#
# Build (requires NGC login for nvcr.io NIM stages + model prefetch):
#   echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
#   export NGC_API_KEY=...
#   ./scripts/docker/build-content-localization-image.sh
# Or manually:
#   ./scripts/docker/prefetch-nim-model-caches.sh
#   docker build -t content-localization:1.2.0-turing .
#
# Push to your organization's private registry (see cai/README.md).

# ---------------------------------------------------------------------------
# Stage 1 — grpcurl (gRPC health checks)
# ---------------------------------------------------------------------------
FROM golang:1.26-bookworm AS grpcurl-builder
ARG GRPCURL_VERSION=v1.9.3
RUN set -eux; \
    git clone --depth 1 -b "${GRPCURL_VERSION}" https://github.com/fullstorydev/grpcurl /src; \
    cd /src; \
    go get golang.org/x/net@v0.57.0; \
    go get golang.org/x/oauth2@v0.36.0; \
    go get google.golang.org/grpc@v1.82.0; \
    go mod tidy; \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/grpcurl ./cmd/grpcurl

# ---------------------------------------------------------------------------
# Stage 2 — Next.js demo UI + ffmpeg
# ---------------------------------------------------------------------------
FROM node:24-alpine AS demo-builder
COPY client/demos/build-ffmpeg.sh /build-ffmpeg.sh
RUN chmod +x /build-ffmpeg.sh && /build-ffmpeg.sh
RUN npm install -g npm@11.18.0 && apk add --no-cache git
WORKDIR /build/demo
COPY client/demos/package.json client/demos/package-lock.json* client/demos/yarn.lock* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY client/demos/ ./
COPY protos ./protos
COPY assets ./assets
ARG NEXT_PUBLIC_INPUT_FILE_NAME=sample_video.mp4
ENV NEXT_PUBLIC_INPUT_FILE_NAME=${NEXT_PUBLIC_INPUT_FILE_NAME} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production
RUN npm run generate-ts-protos && npm run build

# ---------------------------------------------------------------------------
# Stage 3 — NVIDIA NIM microservices (bundled into ContentLocalization image)
# Requires: docker login nvcr.io before build (NGC_API_KEY).
# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 nvcr.io/nim/nvidia/lipsync:1.3.0 AS nim-lipsync
FROM --platform=linux/amd64 nvcr.io/nim/nvidia/active-speaker-detection:1.1.0 AS nim-asd

# ---------------------------------------------------------------------------
# Stage 4 — unified runtime (Cloudera CUDA base + blueprint + NIM bundles)
# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.13-cuda:2026.08.1-b5

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ROOT=/opt/content-localization \
    PIP_ROOT_USER_ACTION=ignore \
    NIM_BUNDLE_ROOT=/opt/nvidia-nim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl wget jq git ca-certificates gnupg \
        docker.io \
        libvpx9 libopus0 \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 (demo runtime + AMP build compatibility)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY --from=grpcurl-builder /out/grpcurl /usr/local/bin/grpcurl
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -sf /root/.local/bin/uv /usr/local/bin/uv

# ffmpeg binaries from demo-builder (Alpine/musl) — install runtime libs on Debian
COPY --from=demo-builder /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=demo-builder /usr/local/lib/libav*.so* /usr/local/lib/
COPY --from=demo-builder /usr/local/lib/libsw*.so* /usr/local/lib/
COPY --from=demo-builder /usr/local/lib/libpostproc*.so* /usr/local/lib/
ENV LD_LIBRARY_PATH=/usr/local/lib

# Copy NIM server trees into isolated prefixes (no Docker socket needed on CAI).
COPY scripts/docker/record-nim-bundle-entrypoint.sh /tmp/record-nim-bundle-entrypoint.sh
COPY scripts/docker/copy-nim-bundle.sh /tmp/copy-nim-bundle.sh
RUN chmod +x /tmp/record-nim-bundle-entrypoint.sh /tmp/copy-nim-bundle.sh
RUN --mount=from=nim-lipsync,source=/,target=/nim-src,readonly \
    bash /tmp/copy-nim-bundle.sh /nim-src "${NIM_BUNDLE_ROOT}/lipsync" lipsync /tmp/record-nim-bundle-entrypoint.sh
RUN --mount=from=nim-asd,source=/,target=/nim-src,readonly \
    bash /tmp/copy-nim-bundle.sh /nim-src "${NIM_BUNDLE_ROOT}/asd" asd /tmp/record-nim-bundle-entrypoint.sh

# Bundled NIM trees are copied from nvcr as root; cdsw must write symlinks under opt/nim/.cache at runtime.
RUN set -eux; \
    for nim in lipsync asd; do \
      rm -rf "${NIM_BUNDLE_ROOT}/${nim}/opt/nim/.cache"; \
    done; \
    chown -R cdsw:cdsw "${NIM_BUNDLE_ROOT}/lipsync" "${NIM_BUNDLE_ROOT}/asd"

# Baked NIM model weights (prefetch on build host — see scripts/docker/prefetch-nim-model-caches.sh).
COPY build/nim-model-cache/lipsync /opt/nvidia-nim/baked-model-cache/lipsync
COPY build/nim-model-cache/asd /opt/nvidia-nim/baked-model-cache/asd
RUN set -eux; \
    test -n "$(ls -A /opt/nvidia-nim/baked-model-cache/lipsync)"; \
    test -n "$(ls -A /opt/nvidia-nim/baked-model-cache/asd)"; \
    chown -R cdsw:cdsw /opt/nvidia-nim/baked-model-cache

WORKDIR ${APP_ROOT}
COPY pyproject.toml uv.lock README.md ./
COPY protos ./protos
COPY src ./src
COPY client ./client
COPY configs ./configs
COPY assets ./assets
COPY cai ./cai
COPY scripts/docker ./scripts/docker

RUN chmod +x scripts/docker/*.sh && \
    uv sync --extra test && \
    bash protos/generate_protos.sh && \
    mkdir -p /opt/nim \
             /var/lib/content-localization/models/lipsync \
             /var/lib/content-localization/models/asd \
             /var/lib/content-localization/demo-app && \
    chown -R cdsw:cdsw ${APP_ROOT} /var/lib/content-localization /opt/nim && \
    usermod -aG docker cdsw || true

# Demo production artifacts (Next.js + custom Node server)
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/dist ./client/demos/dist
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/node_modules ./client/demos/node_modules
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/package.json ./client/demos/package.json
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/.next ./client/demos/.next

ENV PYTHONPATH="${APP_ROOT}:${APP_ROOT}/src:${APP_ROOT}/client:${APP_ROOT}/protos/generated" \
    ML_RUNTIME_EDITION="ContentLocalization" \
    ML_RUNTIME_SHORT_VERSION="1.9" \
    ML_RUNTIME_MAINTENANCE_VERSION=0 \
    ML_RUNTIME_FULL_VERSION="1.9.0-content-localization" \
    ML_RUNTIME_DESCRIPTION="Content Localization with bundled LipSync/ASD NIM servers, CUDA 3.13, Node.js, and grpcurl" \
    LIPSYNC_MODEL_MOUNT_PATH=/home/cdsw/volumes/models/lipsync \
    ASD_MODEL_MOUNT_PATH=/home/cdsw/volumes/models/asd \
    APP_PORT=3000

# Runtime catalog metadata (ENV + LABEL must match; AMP runtimes block uses the same strings).
LABEL com.cloudera.ml.runtime.edition=$ML_RUNTIME_EDITION \
    com.cloudera.ml.runtime.short-version=$ML_RUNTIME_SHORT_VERSION \
    com.cloudera.ml.runtime.maintenance-version=$ML_RUNTIME_MAINTENANCE_VERSION \
    com.cloudera.ml.runtime.full-version=$ML_RUNTIME_FULL_VERSION \
    com.cloudera.ml.runtime.description=$ML_RUNTIME_DESCRIPTION
LABEL org.opencontainers.image.title="Content Localization for Media"
LABEL org.opencontainers.image.description="Unified NVIDIA Content Localization Blueprint image for Docker Hub and Cloudera AI Workbench"

COPY cai/runtime/scripts/cai-runtime-startup.sh /etc/profile.d/content-localization-cai.sh
COPY cai/runtime/scripts/run-bundled-nim.sh /usr/local/bin/run-bundled-nim
COPY cai/runtime/scripts/prepare-bundled-nim-models.sh /usr/local/bin/prepare-bundled-nim-models
RUN chmod +x /etc/profile.d/content-localization-cai.sh \
    /usr/local/bin/run-bundled-nim \
    /usr/local/bin/prepare-bundled-nim-models && \
    echo '[ -f /etc/profile.d/content-localization-cai.sh ] && source /etc/profile.d/content-localization-cai.sh' \
        >> /etc/bash.bashrc

EXPOSE 3000 50050 50054 50055 50056 8004 8005 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${CDSW_APP_PORT:-${APP_PORT:-3000}}/" || exit 1

ENTRYPOINT ["/opt/content-localization/scripts/docker/entrypoint.sh"]
CMD ["stack"]

WORKDIR /home/cdsw
USER cdsw
