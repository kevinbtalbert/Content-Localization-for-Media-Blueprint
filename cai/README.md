# Content Localization on Cloudera AI Workbench

This directory contains the Cloudera AI (CAI) deployment overlay for the NVIDIA Content Localization Blueprint. The upstream blueprint microservices (Controller, S2S, ASD NIM, LipSync NIM, demo UI) are unchanged; CAI-specific automation lives under `cai/`.

## Architecture

CAI projects do **not** have a Docker socket. LipSync and ASD NIM servers are **bundled into the ContentLocalization runtime image** at build time (multi-stage `FROM nvcr.io/nim/...`). GPU applications start the bundled binaries directly — one registered runtime for everything.

```
docker build (with NGC login) → bundles NIMs into ContentLocalization image
AMP Install
  → Prerequisites + Python deps
  → Start LipSync NIM GPU app (ContentLocalization runtime)
  → Start ASD NIM GPU app (ContentLocalization runtime)
  → Start S2S + Controller + Demo UI
```

| Component | Where it runs | Protocol |
|-----------|---------------|----------|
| LipSync NIM | CML GPU Application (bundled in image) | gRPC :50054 |
| ASD NIM | CML GPU Application (bundled in image) | gRPC :50055 |
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
| `NGC_API_KEY` | Yes (at AMP install) | NIM model access inside NIM application pods |
| `S2S_SERVICE` | Yes | `EL_DUBBING` or `CAMB_DUBBING` |
| `ELEVENLABS_API_KEY` | If EL | ElevenLabs dubbing API |
| `CAMB_API_KEY` | If Camb | CambAI dubbing API |

### NGC access

- `nvcr.io/nim/nvidia/active-speaker-detection:1.1.0`
- `nvcr.io/nim/nvidia/lipsync:1.3.0` (requires [NVIDIA AI for Media Private Access](https://developer.nvidia.com/ai-for-media/private-access-program))

## Building the ContentLocalization runtime image

The root [`Dockerfile`](../Dockerfile) produces one image for CAI: blueprint tooling, demo UI, and **bundled LipSync/ASD NIM servers** under `/opt/nvidia-nim/`. Build from the **repository root** on a machine with Docker Desktop (or Docker Engine) running.

### Before you start

| Requirement | Notes |
|-------------|--------|
| Docker daemon running | `docker info` must succeed |
| NGC API key | [Generate](https://org.ngc.nvidia.com/setup/api-key) with access to NIM images |
| LipSync private access | [NVIDIA AI for Media](https://developer.nvidia.com/ai-for-media/private-access-program) for `lipsync:1.3.0` |
| Disk space | Allow **50 GB+** free (NIM stages + final image) |
| Build time | Often **30–90 minutes** depending on network and CPU |
| Platform | Use `--platform linux/amd64` when building on Apple Silicon |

### Credential safety (required)

The NGC API key must **never** appear in git, Docker Hub, or image layers.

| Do | Don't |
|----|--------|
| Export `NGC_API_KEY` in your **terminal session only** | Commit the key to `.env`, scripts, or the Dockerfile |
| Use `docker login nvcr.io` before `docker build` | Pass `--build-arg NGC_API_KEY=...` (can leak into build history) |
| `unset NGC_API_KEY` after login | Paste the key into GitHub issues, PRs, or AMP metadata |
| Set `NGC_API_KEY` again at **CAI AMP install** (project env) for runtime model download | Bake the key into the image with `ENV NGC_API_KEY` |

The Dockerfile pulls NIM source images during build using your **host** `docker login` session — the key is not copied into the final image.

### Build and push

From the repository root:

```bash
# 1. Set key in this shell only (not in any file)
export NGC_API_KEY='<your-ngc-api-key>'

# 2. Authenticate to NVIDIA Container Registry (host credential store only)
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin

# 3. Optional: verify NIM images are reachable before the full build
docker pull --platform linux/amd64 nvcr.io/nim/nvidia/lipsync:1.3.0
docker pull --platform linux/amd64 nvcr.io/nim/nvidia/active-speaker-detection:1.1.0

# 4. Build the unified runtime (linux/amd64 for CAI)
docker build --platform linux/amd64 \
  -t docker.io/<your-dockerhub-user>/contentlocalization:1.2.0 \
  .

# 5. Clear the key from your shell
unset NGC_API_KEY

# 6. Push to your registry (image contains no secrets)
docker push docker.io/<your-dockerhub-user>/contentlocalization:1.2.0
```

Replace `<your-dockerhub-user>` with your registry namespace. Use a private registry instead of Docker Hub if your org requires it.

### Verify the NIM bundle (optional)

After the build, confirm bundled NIM trees exist:

```bash
docker run --rm --platform linux/amd64 \
  docker.io/<your-dockerhub-user>/contentlocalization:1.2.0 \
  bash -lc 'test -f /opt/nvidia-nim/lipsync/entrypoint && test -f /opt/nvidia-nim/asd/entrypoint && echo OK'
```

Expected output: `OK`. If either `entrypoint` file is missing, the NIM copy stages failed — check `docker login nvcr.io` and LipSync registry access, then rebuild.

### What gets baked in vs downloaded later

| At **image build** (your workstation) | At **CAI runtime** (GPU applications) |
|----------------------------------------|----------------------------------------|
| NIM server binaries under `/opt/nvidia-nim/` | NIM **model weights** downloaded on first start |
| Python, Node, grpcurl, blueprint code, demo UI | Uses `NGC_API_KEY` from **project environment** |
| `ML_RUNTIME_EDITION=ContentLocalization` labels | Prerequisite check verifies bundle paths exist |

First LipSync/ASD application start on CAI may take **15–30 minutes** while models download.

## Custom runtime registration (admin)

Register **one** runtime in **Admin → Runtime Catalog**:

1. Update [`repo-assembly.json`](runtime/repo-assembly.json): set `image_identifier` to your pushed tag (e.g. `docker.io/<user>/contentlocalization:1.2.0`).
2. Register using [`METADATA.yaml`](runtime/METADATA.yaml) or upload `repo-assembly.json` under **Site Administration → Runtime**.
3. Confirm catalog fields match the image labels:

| Field | Value |
|-------|-------|
| Editor | JupyterLab |
| Kernel | Python 3.13 |
| Edition | ContentLocalization |
| Version | 1.2 |

Deprecate older `1.1` registrations after cutover.

The image bundles LipSync + ASD NIM servers under `/opt/nvidia-nim/`, plus Python 3.13 CUDA, Node.js 20, grpcurl, uv, the blueprint, and pre-built demo UI.

**Image size:** expect a large image (NIM bundles are multi-GB).

### AMP runtime auto-select

The AMP Configure Project screen picks a runtime by matching `.project-metadata.yaml`:

| Field | Value |
|-------|-------|
| Editor | JupyterLab |
| Kernel | Python 3.13 |
| Edition | ContentLocalization |
| Version | 1.2 |

If Configure Project defaults to **Nvidia GPU / 2026.08**, the custom runtime is not matched. Fix:

1. **Register** the custom image in Runtime Catalog (edition must be unique — not `Nvidia GPU`).
2. **Refresh** the AMP catalog (**Site Administration → AMPs → Refresh**) after pushing metadata updates.
3. On Configure Project, set **Edition** to **ContentLocalization** and leave **Enable Spark** off.
4. Optional: in Runtime Catalog, mark the custom runtime as **Default** (admin).

Rebuild the image after Dockerfile metadata changes so `ML_RUNTIME_*` labels match the table above.

## AMP installation

1. Add `catalog-entry.yaml` to your AMP catalog (or install from git URL).
2. Install the AMP and provide environment variables on the **Configure Project** screen (same pattern as [CML AMP RAG Monitoring](https://github.com/cloudera/CML_AMP_RAG_Monitoring): `default: ""` + `description` only — no `required`, no `null`).
3. The AMP executes tasks defined in [`.project-metadata.yaml`](../.project-metadata.yaml).

### AMP task sequence

1. Install Python deps + generate protos (`cai/amp/1_install/install_dependencies.py`)
2. Validate prerequisites (`cai/amp/0_spike/validate_cai_prerequisites.py`) — reads `os.environ["NGC_API_KEY"]` etc.
3. Record NIM bundle configuration
4. Start LipSync NIM GPU application (ContentLocalization runtime)
5. Start ASD NIM GPU application (ContentLocalization runtime)
6. Start S2S application
7. Wire endpoints (`cai/config/runtime_endpoints.env`)
8. Start Controller application
9. Build Next.js demo
10. Start demo UI application

Enable **Unauthenticated App Access** for the `content-localization-ui` subdomain.

## Phase 0 validation (manual)

On a GPU session before full install:

```bash
python cai/amp/0_spike/validate_cai_prerequisites.py
```

Checks: GPU visibility, `NGC_API_KEY`, bundled NIM trees at `/opt/nvidia-nim/{lipsync,asd}`, Node.js, grpcurl.

## GPU profile

GPU SKU is detected from `nvidia-smi` during the prerequisite session and saved to `cai/config/gpu_profile.json` for reference.

Override `LIPSYNC_NIM_TAGS_SELECTOR` at AMP install for target language (default `language=de`).

## Post-install validation

```bash
# NIM health (pod IP in cai/nim_endpoints.json)
curl -s http://<lipsync-pod-ip>:8004/v1/health/ready
curl -s http://<asd-pod-ip>:8005/v1/health/ready

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
| Prerequisite session: NGC_API_KEY not set | Set at AMP Configure Project or Project Settings → Advanced → Environment, then start a new session |
| Demo UI missing default video | Sample MP4s are not in git; run `bash scripts/misc/fetch_sample_assets.sh` on a dev machine or upload your own to `assets/` |
| Docker daemon not running during build | Start Docker Desktop; `docker info` must work before `docker build` |
| `docker login` or NIM pull fails | Check NGC key and LipSync private access; never commit the key — use `export` in shell only |
| NIM application fails at startup | Verify `NGC_API_KEY`; first start downloads models (15–30 min) |
| Controller cannot reach NIM | Check `cai/config/runtime_endpoints.env` pod IPs; verify network policy allows gRPC between pods |
| AMP timeout on NIM startup | First NIM start downloads models — allow 15–30 min; check NGC key and LipSync private access |
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
