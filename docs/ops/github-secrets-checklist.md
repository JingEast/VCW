# GitHub Secrets Checklist

## Objective
Ensure all required secrets are configured in the GitHub repository before CI/CD activation.

---

## Navigation
`Repository → Settings → Secrets and variables → Actions → New repository secret`

URL: `https://github.com/YOUR_USERNAME/VCW/settings/secrets/actions`

---

## Required Secrets

### Tier 1: Critical (CI/CD will fail without these)

| Secret | Value Source | Used By |
|--------|--------------|---------|
| `DOCKER_USERNAME` | Your Docker Hub username | CI push job, CD deploy jobs |
| `DOCKER_PASSWORD` | Docker Hub Access Token | CI push job, CD deploy jobs |

**How to create Docker Hub Access Token:**
1. Go to https://hub.docker.com/settings/security
2. Click **New Access Token**
3. Name: `vcw-github-actions`
4. Permissions: `Read, Write, Delete`
5. Copy token and paste into GitHub Secret `DOCKER_PASSWORD`

### Tier 2: Recommended

| Secret | Value Source | Used By |
|--------|--------------|---------|
| `CODECOV_TOKEN` | https://app.codecov.io/gh/YOUR_USERNAME/VCW | CI test job (optional) |

### Tier 3: Runtime (application-level, not CI-level)

These are **NOT** stored as GitHub Secrets for the CI workflow. They are runtime environment variables injected via:
- `docker-compose.yml` for local/staging
- Server environment variables for production

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://vcw:vcw@postgres:5432/vcw` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `SECRET_KEY` | Flask secret key | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |

## Verification Commands

After adding secrets, verify locally (secrets are NOT exposed):

```bash
# This will show secrets are present but masked
git push origin main
# Then check GitHub Actions tab for green checkmarks
```

## Failure Symptoms

| Symptom | Missing Secret | Error in Actions Log |
|---------|---------------|---------------------|
| Push job fails | `DOCKER_USERNAME` | `Error: No credentials found` |
| Push job fails | `DOCKER_PASSWORD` | `denied: requested access to the resource is denied` |
| Coverage upload fails | `CODECOV_TOKEN` | `Codecov token not found` |
| Deploy job fails | `DOCKER_USERNAME` | `docker login` fails |

## Troubleshooting

```bash
# If secrets were entered incorrectly, update them:
# Go to Settings → Secrets → Find secret → Update
# There is no CLI command to update secrets; use GitHub web UI
```

## Checklist

- [ ] `DOCKER_USERNAME` added
- [ ] `DOCKER_PASSWORD` added (must be Access Token, not account password)
- [ ] `CODECOV_TOKEN` added (optional)
- [ ] Secrets are marked as `Repository secrets` (not `Environment secrets`)
