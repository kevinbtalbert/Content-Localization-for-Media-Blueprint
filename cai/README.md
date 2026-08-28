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

Register in **Admin → Runtime Catalog** using [`METADATA.yaml`](runtime/METADATA.yaml).

The image includes Python 3.13 CUDA runtime, Docker CLI, Node.js 20, grpcurl, uv, the full blueprint, pre-built demo UI, and Ray/NIM tooling.

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

Checks: Docker daemon, GPU visibility, `NGC_API_KEY`, Node.js, grpcurl.

## Ray cluster configuration

GPU worker SKU and count are set at **AMP install** via project environment variables (see [`.project-metadata.yaml`](../.project-metadata.yaml)):

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAY_GPU_ACCELERATOR_TYPE` | `A10G` | Ray `accelerator_type` label; maps to `nvidia.com/gpu.product` |
| `RAY_GPU_NODE_LABEL_VALUE` | *(auto)* | Override K8s label (e.g. `NVIDIA-A10G`). Use `none` to skip SKU placement |
| `RAY_NIM_GPU_WORKER_COUNT` | `2` | GPU worker pods (one NIM per worker for LipSync + ASD) |

**Common `RAY_GPU_ACCELERATOR_TYPE` values:** `A10G`, `L40S`, `L4`, `T4`, `A100`, `H100`.

Verify your cluster label on a GPU node:

```bash
nvidia-smi --query-gpu=gpu_name --format=csv,noheader
kubectl get nodes -L nvidia.com/gpu.product
```

Fallback YAML defaults live in [`cai/ray/configs/ray_cluster_config.yaml`](ray/configs/ray_cluster_config.yaml) (overridden by the env vars above when set on the project).

Also edit in that file:

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
| Docker-in-Docker unavailable | Run `validate_cai_prerequisites.py`; contact admin for Docker socket access on GPU pods |
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
