# Rollback Execution Guide

## Objective
Roll back a failed deployment to the previous stable version safely.

---

## Automated Rollback (Built-in)

The `scripts/deploy.sh` script automatically rolls back when health checks fail.

### Trigger Conditions
- Health check timeout (default 60s)
- `/health` returns non-200 status
- Container fails to start

### What Happens Automatically
1. Deploy script detects health check failure
2. Reads stable tag from `/tmp/vcw-{env}-stable-tag.txt`
3. Calls `scripts/rollback.sh {env}`
4. Pulls previous image and restarts services
5. Verifies rollback health

---

## Manual Rollback

### When to Use Manual Rollback
- Automated rollback failed
- You need to rollback for reasons other than health (e.g., performance regression)
- The stable tag file is missing

### Step 1: Identify Previous Stable Version

```bash
# Option A: Use Docker Hub latest tag
docker pull $DOCKER_USERNAME/vcw-web:latest

# Option B: Use specific previous version
docker pull $DOCKER_USERNAME/vcw-web:v0.0.0

# Option C: Check GitHub Actions artifacts for previous deployment
# Navigate to: https://github.com/YOUR_USERNAME/VCW/actions
# Find the last successful deployment
```

### Step 2: Execute Rollback

```bash
# Rollback staging
bash scripts/rollback.sh staging

# Rollback production
bash scripts/rollback.sh production
```

### Step 3: Verify Rollback

```bash
# Check health
bash scripts/health-check.sh http://localhost:5000

# Check container status
docker compose ps

# Check logs
docker compose logs web --tail=50
```

---

## GitHub Actions Rollback

If you deployed via GitHub Actions and need to rollback:

### Method 1: Re-run Previous Workflow
1. Go to `https://github.com/YOUR_USERNAME/VCW/actions`
2. Find the last successful **CD** workflow
3. Click **Re-run jobs**
4. Select **Re-run failed jobs** or **Re-run all jobs**

### Method 2: Deploy Previous Tag
```bash
# Checkout previous tag
git checkout v0.0.0

# Push to main (via PR, NOT direct push due to branch protection)
git checkout -b rollback/v0.0.0
git push origin rollback/v0.0.0
# Create PR and merge
```

---

## Rollback Logging

During rollback, these logs are generated:

```
[rollback:production] Rolling back to stable tag: abc12345
[rollback:production] Pulling images...
[rollback:production] Starting services...
[rollback:production] Rollback health check passed
```

If rollback fails:
```
[rollback:production] FAIL: Rollback health check timeout
```

## Failure Symptoms

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No stable tag recorded` | First deployment or file deleted | Manually specify image tag |
| `Failed to pull stable images` | Image not in registry | Tag exists in Docker Hub? |
| `Rollback health check timeout` | Previous version also broken | Go further back in history |
| `docker compose ps` shows `Exit 1` | Container crash | Check logs: `docker compose logs web` |

## Troubleshooting

```bash
# Manual rollback without stable tag file
export IMAGE_TAG=v0.0.0
export DOCKER_USERNAME=your-username
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# If all else fails, reset to base state
docker compose down -v
docker compose up -d
# Then run migrations
python -m alembic upgrade head
```
