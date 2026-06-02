# GitHub Environments Configuration Guide

## Objective
Configure `staging` and `production` environments in GitHub to enable deployment gates and manual approval.

---

## Environment: `staging`

### Navigation
`Repository → Settings → Environments → New environment`

### Configuration
| Field | Value |
|-------|-------|
| Name | `staging` |
| Protection rules | None (auto-deploy) |
| Deployment branches | `main`, `master` |

### Steps
1. Go to `https://github.com/YOUR_USERNAME/VCW/settings/environments`
2. Click **New environment**
3. Name: `staging`
4. Under **Deployment branches**, select `Selected branches`
5. Add pattern: `main`
6. Add pattern: `master`
7. Click **Save protection rules**

---

## Environment: `production`

### Navigation
`Repository → Settings → Environments → New environment`

### Configuration
| Field | Value |
|-------|-------|
| Name | `production` |
| Required reviewers | **1+ reviewer** (e.g., yourself or team lead) |
| Wait timer | 0 minutes |
| Deployment branches | `main`, `master` |

### Steps
1. Go to `https://github.com/YOUR_USERNAME/VCW/settings/environments`
2. Click **New environment**
3. Name: `production`
4. Enable **Required reviewers**
5. Add at least 1 GitHub user as reviewer
6. Under **Deployment branches**, select `Selected branches`
7. Add pattern: `main`
8. Add pattern: `master`
9. Click **Save protection rules**

---

## Environment Variables (Optional)

You can set environment-specific variables:

| Environment | Variable | Example Value |
|-------------|----------|---------------|
| staging | `FLASK_DEBUG` | `false` |
| production | `FLASK_DEBUG` | `false` |

Navigate to each environment → **Environment variables** → Add variable.

## Failure Symptoms

| Symptom | Cause | Fix |
|---------|-------|-----|
| CD workflow stuck on "deploy-production" | No production environment | Create `production` environment |
| "Waiting for review" indefinitely | No reviewers configured | Add reviewers to `production` environment |
| "Deployment not allowed" | Branch not allowed | Add `main` to deployment branches |

## Troubleshooting

```bash
# Verify environments via GitHub CLI (if installed)
gh api repos/:owner/:repo/environments
```
