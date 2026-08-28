# syntax=docker/dockerfile:1
# Unified Content Localization image for Docker Hub and Cloudera AI Workbench.
#
# Build:
#   docker build -t <dockerhub-user>/content-localization:latest .
# Push:
#   docker push <dockerhub-user>/content-localization:latest
#
# Run full stack:
#   docker run --gpus all -v /var/run/docker.sock:/var/run/docker.sock \
#     --env-file configs/elevenlabs.env --env-file .env -p 3000:3000 \
#     <dockerhub-user>/content-localization:latest

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
# Stage 3 — unified runtime (Cloudera CUDA base + blueprint + tooling)
# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.13-cuda:2026.08.1-b5

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ROOT=/opt/content-localization \
    PIP_ROOT_USER_ACTION=ignore

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
    mkdir -p /var/lib/content-localization/models/lipsync \
             /var/lib/content-localization/models/asd \
             /var/lib/content-localization/demo-app && \
    chown -R cdsw:cdsw ${APP_ROOT} /var/lib/content-localization && \
    usermod -aG docker cdsw || true

# Demo production artifacts (Next.js + custom Node server)
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/dist ./client/demos/dist
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/node_modules ./client/demos/node_modules
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/package.json ./client/demos/package.json
COPY --from=demo-builder --chown=cdsw:cdsw /build/demo/.next ./client/demos/.next

ENV PYTHONPATH="${APP_ROOT}:${APP_ROOT}/src:${APP_ROOT}/client:${APP_ROOT}/protos/generated" \
    ML_RUNTIME_EDITION="Content Localization for Media (CUDA 3.13)" \
    LIPSYNC_MODEL_MOUNT_PATH=/var/lib/content-localization/models/lipsync \
    ASD_MODEL_MOUNT_PATH=/var/lib/content-localization/models/asd \
    APP_PORT=3000

# Override CML metadata labels to make this a unique custom runtime
ARG RUNTIME_FULL_VERSION=1.1.0-content-localization
ARG RUNTIME_SHORT_VERSION=1.1
ARG RUNTIME_MAINTENANCE_VERSION=0

LABEL com.cloudera.ml.runtime.edition="${ML_RUNTIME_EDITION}"
LABEL com.cloudera.ml.runtime.full-version="${RUNTIME_FULL_VERSION}"
LABEL com.cloudera.ml.runtime.short-version="${RUNTIME_SHORT_VERSION}"
LABEL com.cloudera.ml.runtime.maintenance-version="${RUNTIME_MAINTENANCE_VERSION}"
LABEL org.opencontainers.image.title="Content Localization for Media"
LABEL org.opencontainers.image.description="Unified NVIDIA Content Localization Blueprint image for Docker Hub and Cloudera AI Workbench"

COPY cai/runtime/scripts/cai-runtime-startup.sh /etc/profile.d/content-localization-cai.sh
RUN chmod +x /etc/profile.d/content-localization-cai.sh && \
    echo '[ -f /etc/profile.d/content-localization-cai.sh ] && source /etc/profile.d/content-localization-cai.sh' \
        >> /etc/bash.bashrc

EXPOSE 3000 50050 50054 50055 50056 8004 8005 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${CDSW_APP_PORT:-${APP_PORT:-3000}}/" || exit 1

ENTRYPOINT ["/opt/content-localization/scripts/docker/entrypoint.sh"]
CMD ["stack"]

WORKDIR /home/cdsw
USER cdsw
