# NIM model cache (build-time only — not stored in git)

Before `docker build`, prefetch LipSync and ASD model weights on a **GPU workstation** with Docker and NGC access. The caches are copied into the ContentLocalization runtime image.

## NVIDIA licensing (required)

Prefetch downloads **NVIDIA NIM model artifacts** from `nvcr.io`. Embedding them in a runtime image does **not** license downstream use.

| Who | Must have |
|-----|-----------|
| **Build operator** | NGC API key with entitlement to LipSync + ASD (LipSync requires [AI for Media Private Access](https://developer.nvidia.com/ai-for-media/private-access-program)) |
| **End customer** | **Their own** NVIDIA NIM / NGC entitlement before deploying the built image |

See [NIMLICENSES.md](../../NIMLICENSES.md). Do not distribute baked-weight images to unlicensed parties.

## What you must provide

| Input | Required? | Example | Notes |
|-------|-----------|---------|-------|
| `NGC_API_KEY` | **Yes** | `nvapi-…` | Build-host only. **Never** baked into the image. Customer supplies their own key at CAI install. |
| GPU on build host | **Yes** | Tesla T4 | Must be a [supported Maxine GPU](#supported-gpus). **Not** A100/H100. |
| `LIPSYNC_NIM_TAGS_SELECTOR` | No | `language=de` | Default in this blueprint. One language per baked cache. |
| `NIM_PREFETCH_GPU` | No | `all` or `device=0` | Which GPU Docker exposes during prefetch. See below. |
| `NIM_PREFETCH_TIMEOUT_S` | No | `7200` | Max seconds to wait for each NIM `/v1/health/ready` |
| `NIM_PREFETCH_MIN_BYTES_LIPSYNC` | No | 3 GiB | Refuse to stage LipSync cache smaller than this after health ready |
| `NIM_PREFETCH_MIN_BYTES_ASD` | No | 2 GiB | Refuse to stage ASD cache smaller than this after health ready |
| `CONTENT_LOCALIZATION_IMAGE` | No | `content-localization:1.7.0-turing` | Override auto-tagging (disables arch suffix) |
| `CONTENT_LOCALIZATION_REGISTRY` | No | `<registry>/<namespace>/content-localization` | Optional second tag for your private registry |

```bash
export NGC_API_KEY=...
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
# optional: export CONTENT_LOCALIZATION_REGISTRY=<registry>/<namespace>/content-localization
./scripts/docker/build-content-localization-image.sh
# → content-localization:1.7.0-turing (+ registry tag when set)
```

Or prefetch only:

```bash
./scripts/docker/prefetch-nim-model-caches.sh
docker build --platform linux/amd64 -t content-localization:1.7.0-turing .
```

## Supported GPUs

LipSync and ASD require **Tensor cores** plus **NVENC and NVDEC** (video encode/decode). NVIDIA documents these as supported:

| Architecture | Example SKUs | Build tag suggestion |
|--------------|--------------|----------------------|
| **Turing** | T4, RTX 20xx | `:1.7.0-turing` |
| **Ampere** | A2, A10, A16, A40, L4 | `:1.7.0-ampere` |
| **Ada** | L40, L40S, RTX 4090 | `:1.7.0-ada` |
| **Blackwell** | B40, RTX 5080/5090 | `:1.7.0-blackwell` |

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
| **Total image (with baked caches)** | **~35–45 GB** | NIM binaries without baked cache are smaller |

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

Prefetch **succeeds only when** each NIM returns `/v1/health/ready` and the staged cache meets the minimum size (defaults: 3 GiB LipSync, 2 GiB ASD). A flat `du` without health ready does **not** complete prefetch — this prevents partial bakes like ~650 M / ~422 M caches.
