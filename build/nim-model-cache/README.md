# NIM model cache (build-time only — not stored in git)

Before `docker build`, prefetch LipSync and ASD model weights on a **GPU workstation** with Docker and NGC access. The caches are copied into the ContentLocalization runtime image.

## What you must provide

| Input | Required? | Example | Notes |
|-------|-----------|---------|-------|
| `NGC_API_KEY` | **Yes** | `nvapi-…` | Same key as `docker login nvcr.io`. **Never** baked into the image. |
| GPU on build host | **Yes** | Tesla T4 | Must be a [supported Maxine GPU](#supported-gpus). **Not** A100/H100. |
| `LIPSYNC_NIM_TAGS_SELECTOR` | No | `language=de` | Default in this blueprint. One language per baked cache. |
| `NIM_PREFETCH_GPU` | No | `all` or `device=0` | Which GPU Docker exposes during prefetch. See below. |
| `CONTENT_LOCALIZATION_IMAGE` | No | `user/content-localization:1.2.0-turing` | Override auto-tagging (disables arch suffix) |
| `CONTENT_LOCALIZATION_REGISTRY` | No | `docker.io/you/content-localization` | Also tags registry copy (`:1.2.0-turing`, `:latest`) |

```bash
export NGC_API_KEY=...
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
# optional registry mirror tags:
# export CONTENT_LOCALIZATION_REGISTRY=docker.io/you/content-localization
./scripts/docker/build-content-localization-image.sh
# → content-localization:1.2.0-turing, content-localization:latest (+ registry tags)
```

Or prefetch only:

```bash
./scripts/docker/prefetch-nim-model-caches.sh
docker build --platform linux/amd64 -t content-localization:1.2.0 .
```

## Supported GPUs

LipSync and ASD require **Tensor cores** plus **NVENC and NVDEC** (video encode/decode). NVIDIA documents these as supported:

| Architecture | Example SKUs | Build tag suggestion |
|--------------|--------------|----------------------|
| **Turing** | T4, RTX 20xx | `:1.2.0-turing` |
| **Ampere** | A2, A10, A16, A40, L4 | `:1.2.0-ampere` |
| **Ada** | L40, L40S, RTX 4090 | `:1.2.0-ada` |
| **Blackwell** | B40, RTX 5080/5090 | `:1.2.0-blackwell` |

**Not supported:** A100, H100, B100 (no NVENC/NVDEC on these datacenter GPUs).

**CAI production:** Build on the **same GPU architecture** you deploy on (e.g. prefetch on a T4 if CAI workers are T4). That bakes TensorRT engines for that arch and avoids a long first-start compile in CAI.

## Approximate sizes

These are planning numbers from NVIDIA Helm guidance (10 Gi PVC per NIM) and typical single-language builds. **Run prefetch once on your machine** — the script prints exact `du` totals.

| Component | Approx. size | Notes |
|-----------|--------------|-------|
| LipSync cache (`language=de`) | **~6–10 GB** | Weights + TensorRT engines for one language profile |
| ASD cache | **~4–8 GB** | Weights + engines |
| NIM server binaries (in image) | **~10–15 GB** | Copied from `nvcr.io/nim/...` at build time |
| Cloudera runtime + app stack | **~8–12 GB** | Python, CUDA base, Node, blueprint code |
| **Total image (with baked caches)** | **~35–45 GB** | Your prior 25 GB build had NIM binaries but **no** baked model cache |

Disk during build: allow **~60 GB free** (prefetch work dirs + Docker layers).

## Does `--gpus all` matter?

**At prefetch time (build host): yes** — the GPU Docker exposes determines which manifest profile and TensorRT engines NIM downloads and compiles.

| Build host | Setting | Effect |
|------------|---------|--------|
| Single GPU (e.g. one T4) | `NIM_PREFETCH_GPU=all` (default) | Same as exposing that one GPU. **Fine.** |
| Multi-GPU, same type | `NIM_PREFETCH_GPU=device=0` | Pin a specific GPU so prefetch is deterministic. |
| Multi-GPU, **mixed types** | **Must pin** | `all` may pick the wrong GPU; use `NIM_PREFETCH_GPU=device=N`. |

**At CAI runtime:** irrelevant. Each GPU application gets one GPU from the platform; the image does not use `--gpus all`.

## “General purpose” across GPU types

There is **no single baked cache** that gives zero cold-start on every supported GPU. TensorRT engines are **architecture-specific** (Turing ≠ Ada).

| Strategy | Pros | Cons |
|----------|------|------|
| Build on **same arch as production** (recommended) | Fast CAI startup, no NGC at runtime | One image tag per arch if fleet is mixed |
| One image built on T4, run on L40 | One image to maintain | **First start on L40** recompiles engines (~5–15 min); weights are reused from bake |
| Per-arch tags (`:turing`, `:ada`) | Clear ops, fastest everywhere | Build/push once per arch |

The blueprint defaults to **`language=de`**. Other languages need a different `LIPSYNC_NIM_TAGS_SELECTOR` at prefetch time and a rebuild.

## Output layout

```
build/nim-model-cache/
  lipsync/    → /opt/nvidia-nim/baked-model-cache/lipsync
  asd/        → /opt/nvidia-nim/baked-model-cache/asd
```

Plain `docker build` **fails** if these directories are empty.
