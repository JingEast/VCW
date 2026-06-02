# First Release Execution Guide

## Objective
Execute the first semantic version release (`v0.0.1`) and verify the complete release pipeline.

---

## Prerequisites

- [ ] Code pushed to `main`
- [ ] GitHub Secrets configured (`DOCKER_USERNAME`, `DOCKER_PASSWORD`)
- [ ] GitHub Environments created (`staging`, `production`)
- [ ] Branch protection applied to `main`

---

## Step 1: Create Version Tag

```bash
# Ensure you are on main and up-to-date
git checkout main
git pull origin main

# Generate version (defaults to patch bump)
bash scripts/version.sh patch
# Output: v0.0.1

# Create annotated tag
git tag -a v0.0.1 -m "Release v0.0.1"

# Push tag to trigger Release workflow
git push origin v0.0.1
```

## Step 2: Verify CI Pipeline

Navigate to: `https://github.com/YOUR_USERNAME/VCW/actions`

Expected execution order:
1. **CI workflow** triggers on `push` to `main` (if this is the first push)
2. **Release workflow** triggers on `push` tag `v0.0.1`
3. **CD workflow** triggers on `workflow_run` CI completion

### Expected CI Stages (all green):
| Stage | Duration | Success Indicator |
|-------|----------|-------------------|
| lint | ~1 min | `flake8 OK` + `mypy OK` |
| test | ~3 min | `517 passed` |
| migration-check | ~30 sec | `Schema and models are in sync` |
| docker-smoke | ~2 min | `All Docker smoke checks passed` |
| push | ~1 min | `docker push` succeeds |

### Expected CD Stages:
| Stage | Duration | Success Indicator |
|-------|----------|-------------------|
| deploy-staging | ~1 min | `Deployment completed successfully` |
| health-check | ~30 sec | `Health check passed (HTTP 200)` |

## Step 3: Verify Docker Hub

Navigate to: `https://hub.docker.com/r/YOUR_USERNAME/vcw-web/tags`

Expected tags:
- `latest`
- `v0.0.1` (or short SHA)

Repeat for:
- `YOUR_USERNAME/vcw-worker`
- `YOUR_USERNAME/vcw-beat`

## Step 4: Verify GitHub Release

Navigate to: `https://github.com/YOUR_USERNAME/VCW/releases`

Expected:
- Release `v0.0.1`
- Auto-generated changelog
- Source code archives attached

## Failure Symptoms

| Symptom | Stage | Fix |
|---------|-------|-----|
| `flake8` fails | lint | Fix code style locally, push again |
| `mypy` fails | lint | Fix type errors, push again |
| Tests fail | test | Run `pytest tests/` locally, fix failures |
| `Schema drift detected` | migration-check | Run `alembic revision --autogenerate` if needed |
| `docker build` fails | docker-smoke | Check `Dockerfile` syntax |
| `docker push` fails | push | Verify `DOCKER_USERNAME` and `DOCKER_PASSWORD` secrets |
| `denied` | push | Docker Hub token may lack write permissions |
| `Waiting for review` | deploy-production | Normal — click **Approve and deploy** in GitHub UI |

## Troubleshooting

```bash
# If tag push fails
git push origin v0.0.1 --force-with-lease

# If CI fails, delete tag and retry after fix
git tag -d v0.0.1
git push origin --delete v0.0.1
# Fix code, then recreate tag

# Check workflow logs
git push origin main
# Then go to Actions tab and click failed workflow
```
