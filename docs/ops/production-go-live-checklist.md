# Production Go-Live Checklist

## Objective
Ensure all gates are passed before declaring the application ready for production traffic.

---

## Pre-Deployment Checklist

### Repository Setup
- [ ] GitHub repository created and linked
- [ ] Remote `origin` configured: `git remote -v`
- [ ] Default branch is `main`

### GitHub Environments
- [ ] Environment `staging` created
- [ ] Environment `production` created
- [ ] `production` has 1+ required reviewers
- [ ] Both environments allow deployment from `main` and `master`

### GitHub Secrets
- [ ] `DOCKER_USERNAME` added (Repository secret)
- [ ] `DOCKER_PASSWORD` added (Docker Hub Access Token, NOT account password)
- [ ] `CODECOV_TOKEN` added (optional)

### Branch Protection
- [ ] Protection rule for `main` created
- [ ] Require pull request before merging: enabled
- [ ] Require approvals: 1
- [ ] Require status checks: enabled
- [ ] Status checks selected: `lint`, `test`, `migration-check`, `docker-smoke`
- [ ] Require linear history: enabled
- [ ] Allow force pushes: disabled
- [ ] Allow deletions: disabled

### CI/CD Validation
- [ ] Push to `main` triggers CI workflow
- [ ] CI all stages pass (lint, test, migration-check, docker-smoke, push)
- [ ] Docker images published to Docker Hub
- [ ] CD staging deployment succeeds
- [ ] Staging health check returns HTTP 200
- [ ] Staging Alembic check passes (zero drift)

### Release Validation
- [ ] First tag `v0.0.1` created and pushed
- [ ] GitHub Release auto-generated
- [ ] Changelog generated

---

## Deployment Execution

### Step 1: Trigger Production Deployment

Production deploys only via manual `workflow_dispatch`:

1. Go to `https://github.com/YOUR_USERNAME/VCW/actions/workflows/cd.yml`
2. Click **Run workflow**
3. Select branch: `main`
4. Environment: `production`
5. Click **Run workflow**
6. Wait for required reviewer approval
7. Reviewer clicks **Approve and deploy**

### Step 2: Monitor Deployment

Watch these steps in real-time:
- [ ] `deploy-production` job starts
- [ ] Docker images pulled successfully
- [ ] Services start successfully
- [ ] Health check passes
- [ ] Alembic migration check passes
- [ ] Release tag created

### Step 3: Post-Deployment Verification

| Check | Command / URL | Expected |
|-------|--------------|----------|
| Health | `curl http://YOUR_SERVER:5000/health` | `{"status":"ok"}` |
| Metrics | `curl http://YOUR_SERVER:5000/metrics` | Prometheus format |
| Web UI | `http://YOUR_SERVER:5000` | Page loads |
| Logs | `docker compose logs web --tail=50` | No ERROR |

---

## Rollback Readiness

- [ ] `scripts/rollback.sh` exists and syntax valid
- [ ] Previous stable image tag known (in Docker Hub or `/tmp/vcw-production-stable-tag.txt`)
- [ ] Team knows rollback command: `bash scripts/rollback.sh production`
- [ ] Database backups configured (if production data exists)

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| DevOps | | | |
| QA | | | |
| Product Owner | | | |

---

## After Go-Live

- [ ] Monitor GitHub Actions for 24h
- [ ] Monitor Docker Hub for image pull rates
- [ ] Monitor application logs for errors
- [ ] Document any issues in CHANGELOG.md
- [ ] Schedule next release planning

## Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| On-call engineer | | |
| DevOps lead | | |
| Infrastructure | | |
