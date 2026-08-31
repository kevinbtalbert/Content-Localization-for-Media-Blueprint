# Content Localization on Cloudera AI Workbench

This directory contains the Cloudera AI (CAI) deployment overlay for the NVIDIA Content Localization Blueprint. The upstream blueprint microservices (Controller, S2S, ASD NIM, LipSync NIM, demo UI) are unchanged; CAI-specific automation lives under `cai/`.

## Architecture

```
AMP Install
  → Prerequisites + Python deps + NIM image pull
  → Ray cluster (head + 2 GPU workers)
  → Deploy ASD + LipSync NIMs via Ray NIM engine
  → Start S2S + Controller CML Applications
  → Wire gRPC endpoints → Build + start Next.js UI
```

| Component | Where it runs | Protocol |
|-----------|---------------|----------|
| LipSync NIM | Ray GPU worker (Docker container) | gRPC :50054 |
| ASD NIM | Ray GPU worker (Docker container) | gRPC :50055 |
| S2S | CML Application (CPU) | gRPC :50050 |
| Controller | CML Application (CPU) | gRPC :50056 |
| Demo UI | CML Application | HTTP/WebSocket |

## Prerequisites

### Platform

- Cloudera AI Workbench with **at least 2 GPUs** (one per NIM)
- Outbound internet for NGC (`nvcr.io`) and S2S APIs (ElevenLabs or CambAI)
- Project-scoped CML API key (`CDSW_APIV2_KEY`) available to AMP jobs

### NVIDIA / third-party credentials

| Variable | Required | Purpose |
|----------|----------|---------|
| `NGC_API_KEY` | Yes | Pull NIM images from `nvcr.io` |
| `S2S_SERVICE` | Yes | `EL_DUBBING` or `CAMB_DUBBING` |
| `ELEVENLABS_API_KEY` | If EL | ElevenLabs dubbing API |
| `CAMB_API_KEY` | If Camb | CambAI dubbing API |

### NGC access

- `nvcr.io/nim/nvidia/active-speaker-detection:1.1.0`
- `nvcr.io/nim/nvidia/lipsync:1.3.0` (requires [NVIDIA AI for Media Private Access](https://developer.nvidia.com/ai-for-media/private-access-program))

## Custom runtime registration (admin)

Build and push the **single unified image** from the repository root:

```bash
docker build -t <registry>/content-localization:latest .
docker push <registry>/content-localization:latest
```

Register in **Admin → Runtime Catalog** using [`METADATA.yaml`](runtime/METADATA.yaml) and optionally [`repo-assembly.json`](runtime/repo-assembly.json) (replace `REPLACE_WITH_YOUR_IMAGE` with your pushed image, then add the raw GitHub URL under **Site Administration → Runtime**).

The image includes Python 3.13 CUDA runtime, Docker CLI, Node.js 20, grpcurl, uv, the full blueprint, pre-built demo UI, and Ray/NIM tooling.

### AMP runtime auto-select

The AMP Configure Project screen picks a runtime by matching `.project-metadata.yaml`:

| Field | Value |
|-------|-------|
| Editor | JupyterLab |
| Kernel | Python 3.13 |
| Edition | ContentLocalization |
| Version | 1.1 |

If Configure Project defaults to **Nvidia GPU / 2026.08**, the custom runtime is not matched. Fix:

1. **Register** the custom image in Runtime Catalog (edition must be unique — not `Nvidia GPU`).
2. **Refresh** the AMP catalog (**Site Administration → AMPs → Refresh**) after pushing metadata updates.
3. On Configure Project, set **Edition** to **ContentLocalization** and leave **Enable Spark** off.
4. Optional: in Runtime Catalog, mark the custom runtime as **Default** (admin).

Rebuild the image after Dockerfile metadata changes so `ML_RUNTIME_*` labels match the table above.

## AMP installation

1. Add `catalog-entry.yaml` to your AMP catalog (or install from git URL).
2. Install the AMP and provide environment variables at install time.
3. The AMP executes tasks defined in [`.project-metadata.yaml`](../.project-metadata.yaml).

### AMP task sequence

1. Validate prerequisites (`cai/amp/0_spike/validate_cai_prerequisites.py`)
2. Install Python deps + generate protos
3. Pull NIM Docker images
4. Setup Ray + NIM engine venvs
5. Launch Ray cluster job
6. Deploy NIMs via Ray Management API
7. Start S2S application
8. Wire endpoints (`cai/config/runtime_endpoints.env`)
9. Start Controller application
10. Build Next.js demo
11. Start demo UI application

Enable **Unauthenticated App Access** for the `content-localization-ui` subdomain.

## Phase 0 validation (manual)

On a GPU session before full install:

```bash
python cai/amp/0_spike/validate_cai_prerequisites.py
```

Checks: Docker daemon, GPU visibility, GPU profile detection (`cai/config/gpu_profile.json`), `NGC_API_KEY`, Node.js, grpcurl.

## Ray cluster configuration

GPU worker SKU is **detected automatically** from `nvidia-smi` during the prerequisite validation session (which runs on a GPU) and saved to `cai/config/gpu_profile.json`. The Ray cluster launch job reads that file to set `accelerator_type` and the Kubernetes `nvidia.com/gpu.product` node selector.

Override worker count at AMP install via `RAY_NIM_GPU_WORKER_COUNT` (default `2` — one GPU worker each for LipSync and ASD).

To inspect what was detected:

```bash
cat cai/config/gpu_profile.json
nvidia-smi --query-gpu=gpu_name --format=csv,noheader
```

Edit [`cai/ray/configs/ray_cluster_config.yaml`](ray/configs/ray_cluster_config.yaml) for:

- `cai.head_runtime_identifier` / `worker_runtime_identifier` — match registered custom runtime
- `cai.head_app_name` — Ray head subdomain (or set `RAY_HEAD_APP_NAME` at AMP install)

## NIM deployment configs

- [`cai/ray/configs/nim_deploy/lipsync-nim.json`](ray/configs/nim_deploy/lipsync-nim.json)
- [`cai/ray/configs/nim_deploy/asd-nim.json`](ray/configs/nim_deploy/asd-nim.json)

Override `LIPSYNC_NIM_TAGS_SELECTOR` at AMP install for target language (default `language=de`).

## Post-install validation

```bash
# Ray Management API
curl -s https://content-localization-ray-head.<CDSW_DOMAIN>/api/v1/health

# NIM health (from worker pod IP in cai/nim_endpoints.json)
curl -s http://<worker-ip>:8004/v1/health/ready   # LipSync
curl -s http://<worker-ip>:8005/v1/health/ready   # ASD

# Demo UI
open https://content-localization-ui.<CDSW_DOMAIN>
```

## Local development (Docker Compose)

The unified image runs the full stack in one container (NIM sidecars + S2S + Controller + UI):

```bash
docker build -t content-localization:latest .
docker compose --env-file configs/elevenlabs.env --env-file .env up
```

Requires Docker socket mount, NVIDIA runtime, and 2 GPUs for ASD + LipSync NIMs.

See the main [README.md](../README.md) for additional local development options.

## Troubleshooting

| Issue | Action |
|-------|--------|
| Prerequisite session: docker/node/grpcurl not found | Set project runtime to **ContentLocalization** (custom image from root `Dockerfile`), not stock Nvidia GPU |
| Prerequisite session: NGC_API_KEY not set | Add under **Project Settings → Advanced → Environment** (AMP install values are not always visible to sessions) |
| NIM pull fails | Verify `NGC_API_KEY` and LipSync private access |
| Controller cannot reach NIM | Check `cai/config/runtime_endpoints.env` pod IPs; verify network policy allows gRPC between pods |
| AMP timeout on NIM deploy | Increase job timeout; pre-pull images in install session |
| Single GPU only | Deploy LipSync only; use `bypass_asd=True` in client requests |

## Directory layout

```
cai/
├── amp/           # AMP session and application entry points
├── config/        # Generated runtime_endpoints.env (gitignored)
├── lib/           # Shared helpers
├── ray/           # Ray cluster + NIM engine (adapted from ray-serve-cai)
└── runtime/       # Custom runtime Dockerfiles
```
