# Self-Hosting Langfuse vs Cloud

> **Estimated reading time:** 7 minutes

## Overview

Langfuse gives you a genuine choice: run it yourself or let them run it. Both options use identical code — the self-hosted version is the same as cloud, just operated by you. Here's how to decide, and how to set up each.

## Decision Framework

The choice comes down to three questions:

**1. How sensitive is your data?**
LLM traces contain your prompts and completions — which often contain user-submitted content, internal knowledge, or personally identifiable information. If your legal or compliance team would object to that data leaving your infrastructure, self-host.

**2. What's your ops capacity?**
Self-hosting Langfuse means running Docker Compose with Postgres, ClickHouse, MinIO, and Redis. It's not complex, but it needs monitoring, backups, and upgrades. If you don't have that capacity, cloud is worth the cost.

**3. What's your trace volume?**
Cloud Hobby: free, 50k traces/month — fine for development and small products.
Cloud Pro: $59/mo, unlimited traces — worth it if you're paying for API calls at that scale.
Self-hosted: unlimited, you pay for infra (~$20-40/mo for a small VPS).

## Self-Hosted: Docker Compose Setup

The canonical self-hosted setup runs in 20 minutes:

```bash
# Clone the official docker-compose
curl -fsSL https://raw.githubusercontent.com/langfuse/langfuse/main/docker-compose.yml \
  -o ~/langfuse/docker-compose.yml
cd ~/langfuse

# Create .env
cat > .env << 'EOF'
# Required
NEXTAUTH_SECRET=$(openssl rand -base64 32)
NEXTAUTH_URL=http://localhost:3000
DATABASE_URL=postgresql://langfuse:langfuse@db:5432/langfuse
SALT=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Optional: SMTP for user invites
# SMTP_HOST=smtp.example.com
# SMTP_USER=...
# SMTP_PASSWORD=...
EOF

docker compose up -d
```

Services started:
- `web` — Next.js UI + API on port 3000
- `db` — Postgres 15
- `clickhouse` — ClickHouse for analytics data
- `minio` — S3-compatible object storage for blobs
- `redis` — Queue and cache

Point your SDK at `http://localhost:3000` (or your VPS IP). Done.

**Production considerations:**
- Reverse proxy (Nginx/Caddy) with TLS
- Postgres backups (at minimum: daily pg_dump, preferably WAL streaming)
- ClickHouse and MinIO are lower priority for backups (traces are observable, not business-critical)
- Pin the Langfuse image version in docker-compose to avoid surprise upgrades

## Cloud Setup

1. Go to `cloud.langfuse.com`
2. Sign up with GitHub or Google
3. Create an organisation → create a project
4. Get your API keys from Settings → API Keys

```typescript
const langfuse = new Langfuse({
  publicKey: "pk-lf-...",
  secretKey: "sk-lf-...",
  baseUrl: "https://cloud.langfuse.com",
});
```

Data region: Choose EU (`cloud.langfuse.com`) or US (`us.cloud.langfuse.com`) at project creation. This can't be changed later — choose based on where your users and data residency requirements are.

## Hybrid: Split by Environment

A practical pattern: **local dev → self-hosted staging → cloud production**.

```typescript
const langfuse = new Langfuse({
  publicKey: process.env.LANGFUSE_PUBLIC_KEY!,
  secretKey: process.env.LANGFUSE_SECRET_KEY!,
  baseUrl: process.env.LANGFUSE_BASE_URL ?? "https://cloud.langfuse.com",
});
```

Your `.env.local` points to `http://localhost:3100`. Your production secrets (set as Fly.io/Railway/etc. env vars) point to cloud. Same SDK call, zero code changes.

This is exactly how SandSync works:
- Local: `LANGFUSE_BASE_URL=http://localhost:3100` (self-hosted Docker)
- Production: `LANGFUSE_BASE_URL=https://cloud.langfuse.com` (Fly.io secret)

## Upgrading Self-Hosted

```bash
cd ~/langfuse
docker compose pull
docker compose up -d
```

Langfuse runs database migrations on startup — no manual migration needed. Check the release notes for breaking changes before upgrading.

The Langfuse team releases roughly weekly. Subscribe to their GitHub releases page if you're self-hosting in production.

## Cost Comparison

At 100k traces/month with average 3 generations per trace:

| Option | Monthly Cost | Notes |
|---|---|---|
| Self-hosted (2GB VPS) | ~$12-20 | Hetzner/DigitalOcean + minimal ClickHouse |
| Self-hosted (4GB VPS) | ~$25-40 | More comfortable headroom |
| Cloud Hobby | $0 | 50k trace limit |
| Cloud Pro | $59 | Unlimited, SSO, priority support |

For most early-stage products, Cloud Hobby → Cloud Pro is the right progression. Self-hosting makes sense at scale (>1M traces/month) or with strict data residency requirements.

## Summary

- Self-host if: sensitive data, compliance requirements, or high trace volume where infra cost beats cloud cost
- Cloud if: fast start, no ops overhead, under 50k traces/mo (free) or willing to pay $59/mo
- The hybrid pattern (local self-hosted + production cloud) is practical and zero extra code
- Always set `LANGFUSE_BASE_URL` as an env var — never hardcode it
