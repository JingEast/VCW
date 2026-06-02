# Staging Deployment Verification Guide

## Objective
Verify that the staging deployment succeeds and all health/readiness probes pass.

---

## Trigger Staging Deployment

Staging deploys automatically when CI completes successfully on `main`.

### Manual Trigger (if needed)
Navigate to: `https://github.com/YOUR_USERNAME/VCW/actions/workflows/cd.yml`

1. Click **Run workflow**
2. Select branch: `main`
3. Environment: `staging`
4. Click **Run workflow**

---

## Verification Steps

### Step 1: Check GitHub Actions CD Run

Navigate to: `https://github.com/YOUR_USERNAME/VCW/actions`

Look for workflow: **CD**

Expected jobs:
| Job | Status | Duration |
|-----|--------|----------|
| deploy-staging | ✅ Success | ~2 min |

### Step 2: Check Deployment Logs

In the `deploy-staging` job, expand **Deploy to staging** step:

Expected output:
```
[deploy:staging] Starting deployment...
[deploy:staging] Image tag: abc12345
[deploy:staging] Pulling images...
[deploy:staging] Starting services...
[deploy:staging] Health check (timeout 60s)...
[deploy:staging] Health check passed
[deploy:staging] Deployment completed successfully
```

### Step 3: Health Probe Verification

In the **Health check** step:

Expected output:
```
[health-check] Checking http://localhost:5000/health (timeout 60s)...
[health-check] Attempt 1: HTTP 200, retrying...
[health-check] Health check passed (HTTP 200)
{
    "status": "ok",
    "celery": {
        "status": "ok"
    }
}
```

### Step 4: Migration Safety Check

In the **Alembic migration check** step:

Expected output:
```
[check-migrations] Step 1/2: alembic upgrade head
[check-migrations] upgrade head: OK
[check-migrations] Step 2/2: alembic check
[check-migrations] Schema and models are in sync
```

---

## Readiness / Liveness Probes

| Probe | Endpoint | Expected | Checked By |
|-------|----------|----------|------------|
| Readiness | `GET /health` | HTTP 200, `status=ok` | CD health-check step |
| Liveness | `GET /health` | HTTP 200 | Docker HEALTHCHECK in Dockerfile |
| Metrics | `GET /metrics` | HTTP 200, Prometheus format | Manual verification |

---

## Local Staging Simulation

If you want to test staging deployment locally:

```bash
# Set environment
export IMAGE_TAG=latest
export DOCKER_USERNAME=your-dockerhub-username

# Run staging deployment locally
bash scripts/deploy.sh staging latest

# Verify health
bash scripts/health-check.sh http://localhost:5000

# Verify migrations
python scripts/check_migrations.py
```

## Failure Symptoms

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Health check timeout` | Services not starting | Check Docker logs: `docker compose logs web` |
| `HTTP 503` on `/health` | Redis/PostgreSQL not ready | Wait longer or check infra services |
| `Schema drift detected` | Model changed without migration | Run `alembic revision --autogenerate` |
| `Failed to pull images` | Docker Hub auth failed | Verify `DOCKER_USERNAME` / `DOCKER_PASSWORD` |
| `no such column` | Migration not applied | Run `alembic upgrade head` |

## Troubleshooting

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f postgres
docker compose logs -f redis

# Restart specific service
docker compose restart web

# Full reset (DESTROYS DATA)
docker compose down -v
docker compose up -d
```
