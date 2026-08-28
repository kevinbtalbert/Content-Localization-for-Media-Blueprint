# Demo Web Application

A Next.js-based web interface for the Content Localization Blueprint with video upload, real-time processing, and output preview.

## Quick Start

### Docker (Recommended)

From the project root:

```bash
docker compose --profile demo-app-third-party-s2s \
    --env-file configs/elevenlabs.env \
    --env-file .env \
    up --build
```

Please select the profile name and environment file to suit your needs.

Access at: `http://localhost:3000`

### Local Development

**Prerequisites:** Node.js 24.x, Controller service running, FFmpeg installed

```bash
npm install
npm run generate-ts-protos
npm run dev
```

## Documentation

**Detailed documentation:** [docs/source/demo_app.rst](../../docs/source/demo_app.rst)

**Main project README:** [README.md](../../README.md)
