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
| `NGC_API_KEY` | Yes (at AMP install) | **NVIDIA NIM entitlement** — required for LipSync/ASD even when weights are baked into the runtime image (see [NVIDIA model licensing](#nvidia-model-licensing-baked-weights)) |
| `S2S_SERVICE` | Yes | `EL_DUBBING` or `CAMB_DUBBING` |
| `ELEVENLABS_API_KEY` | If EL | ElevenLabs dubbing API |
| `CAMB_API_KEY` | If Camb | CambAI dubbing API |

### NGC access

- `nvcr.io/nim/nvidia/active-speaker-detection:1.1.0`
- `nvcr.io/nim/nvidia/lipsync:1.3.0` (requires [NVIDIA AI for Media Private Access](https://developer.nvidia.com/ai-for-media/private-access-program))

## NVIDIA model licensing (baked weights)

The ContentLocalization runtime image **embeds LipSync and ASD model weights** at build time. NVIDIA NIM models remain **separately licensed** — baking does not grant or transfer rights to downstream users.

| Party | Requirement |
|-------|-------------|
| **Image builder** | Valid NGC API key with entitlement to pull LipSync/ASD NIM images and model artifacts from `nvcr.io` |
| **End customer / deployer** | **Must independently hold** NVIDIA NIM licensing and NGC entitlement for LipSync and ASD before deploying or using the runtime image |
| **Distribution** | Do not ship the built image to organizations that lack applicable NVIDIA agreements |

Full terms: [NIMLICENSES.md](../NIMLICENSES.md) and NVIDIA [Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/) / [AI product terms](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-ai-products/).

Customers configure their own **`NGC_API_KEY`** at CAI AMP install. That key confirms entitled access; it is not baked into the image.

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

The NGC API key must **never** appear in git, public container registries, or image layers.

| Do | Don't |
|----|--------|
| Export `NGC_API_KEY` in your **terminal session only** | Commit the key to `.env`, scripts, or the Dockerfile |
| Use `docker login nvcr.io` before `docker build` | Pass `--build-arg NGC_API_KEY=...` (can leak into build history) |
| `unset NGC_API_KEY` after login | Paste the key into git, issues, PRs, or AMP metadata |
| Require each **customer** to supply their own entitled `NGC_API_KEY` at CAI AMP install | Bake the key into the image with `ENV NGC_API_KEY` |
| Push the runtime image only to **your organization's private registry** | Publish images containing baked NIM weights to public registries |

The Dockerfile pulls NIM source images during build using your **host** `docker login` session — the key is not copied into the final image.

### Build and push

From the repository root on a **GPU build host** with valid NVIDIA entitlement:

```bash
export NGC_API_KEY='<your-ngc-api-key>'
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin

# Optional: tag for your private registry at build time
# export CONTENT_LOCALIZATION_REGISTRY=<registry-host>/<namespace>/content-localization

./scripts/docker/build-content-localization-image.sh
# → content-localization:1.6.0-<gpu-arch>  (e.g. :1.6.0-turing)

unset NGC_API_KEY

# Push to your organization's registry (not documented here — use your internal process)
docker push <registry>/<namespace>/content-localization:1.6.0-turing
```

Only distribute the pushed image to customers who hold their own NVIDIA NIM / NGC entitlement for LipSync and ASD.

### Verify the NIM bundle (optional)

After the build, confirm bundled NIM trees exist:

```bash
docker run --rm --platform linux/amd64 \
  <your-runtime-image>:1.6.0-turing \
  bash -lc 'test -f /opt/nvidia-nim/lipsync/entrypoint && test -f /opt/nvidia-nim/asd/entrypoint && echo OK'
```

Expected output: `OK`. If either `entrypoint` file is missing, the NIM copy stages failed — check `docker login nvcr.io` and LipSync registry access, then rebuild.

### What gets baked in vs downloaded later

| At **image build** (GPU workstation) | At **CAI runtime** (GPU applications) |
|----------------------------------------|----------------------------------------|
| NIM server binaries under `/opt/nvidia-nim/` | Bundled NIM **exec** (no `docker run` in CAI) |
| **Model weights** under `/opt/nvidia-nim/baked-model-cache/` via prefetch | Seeds `/home/cdsw/volumes/models/{lipsync,asd}` from baked cache on first start |
| Python, Node, grpcurl, blueprint code, demo UI | May recompile TensorRT engines if pod GPU **architecture** differs from build GPU |

**Build inputs (see [build/nim-model-cache/README.md](../build/nim-model-cache/README.md) for full detail):**

| You provide | Example | Required? |
|-------------|---------|-----------|
| `NGC_API_KEY` | `nvapi-…` | Yes (build host only; not in image) |
| GPU on build laptop/workstation | Tesla **T4** | Yes — must be [Maxine-supported](https://docs.nvidia.com/nim/maxine/lipsync/1.3.0/support-matrix.html) (T4, L4, A10, L40, …). **Not** A100/H100. |
| `LIPSYNC_NIM_TAGS_SELECTOR` | `language=de` | No (default) |
| `NIM_PREFETCH_GPU` | `all` or `device=0` | No — pin `device=N` on multi-GPU hosts |

**Approximate image size:** ~35–45 GB with baked caches (~25 GB without). Prefetch prints exact LipSync/ASD cache sizes.

**GPU architecture:** Build on the **same class** as CAI (e.g. T4 → tag `content-localization:1.6.0-turing`). One image runs on other supported GPUs, but a different arch may spend 5–15 minutes recompiling engines on first start.

**Build with models (required for CAI):**

```bash
export NGC_API_KEY=...
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
./scripts/docker/build-content-localization-image.sh
```

Prefetch alone (before a manual `docker build`):

```bash
./scripts/docker/prefetch-nim-model-caches.sh
```

Plain `docker build` without prefetch **fails** — `build/nim-model-cache/` must contain LipSync and ASD weights.

## Custom runtime registration (admin)

Register **one** runtime in **Admin → Runtime Catalog**:

1. Update [`repo-assembly.json`](runtime/repo-assembly.json): set `image_identifier` to your private registry URI (e.g. `<registry>/<namespace>/content-localization:1.6.0-turing`).
2. Register using [`METADATA.yaml`](runtime/METADATA.yaml) or upload `repo-assembly.json` under **Site Administration → Runtime**.
3. Confirm catalog fields match the image labels:

| Field | Value |
|-------|-------|
| Editor | JupyterLab |
| Kernel | Python 3.13 |
| Edition | ContentLocalization |
| Version | 1.6 |

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
| Version | 1.6 |

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
| NIM exits after Triton banner, no `:8004`/`:8005` | **Bundled launcher** runs `nvidia_entrypoint.sh` with a wrapper under `opt/nim/` that execs NIM `python3` + `start_server` (not bare entrypoint, not raw python args — entrypoint prepends `opt/nim/` to relative paths). **`ModuleNotFoundError: nimlib`** or **bundled NIM Python not found** → rebuild the runtime image: `copy-nim-bundle.sh` dereferences `python3` symlinks and copies `usr/bin` + `usr/lib` from the nvcr.io NIM stage. |
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
