# GitHub Repository Setup Guide

## Objective
Link the local VCW repository to GitHub and configure the basic repository settings required for CI/CD activation.

---

## Step 1: Create GitHub Repository

1. Open https://github.com/new
2. Enter **Repository name**: `VCW`
3. Select **Visibility**: `Public` or `Private`
4. **DO NOT** initialize with README, .gitignore, or LICENSE (local repo already has these)
5. Click **Create repository**

## Step 2: Link Local Repository

Run these commands in the project root:

```bash
# Add GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/VCW.git

# Or via SSH (recommended for production)
git remote add origin git@github.com:YOUR_USERNAME/VCW.git

# Rename branch to main
git branch -M main

# Push code
git push -u origin main
```

## Step 3: Verify Repository Settings

Navigate to: `https://github.com/YOUR_USERNAME/VCW/settings`

| Setting | Recommended Value |
|---------|-------------------|
| Default branch | `main` |
| Squash merging | Enabled |
| Rebase merging | Disabled (keep linear history clean) |
| Allow auto-merge | Disabled |
| Automatically delete head branches | Enabled |

## Step 4: Verify Actions Permissions

Navigate to: `Settings → Actions → General`

| Setting | Value |
|---------|-------|
| Actions permissions | Allow all actions and reusable workflows |
| Workflow permissions | Read and write permissions |
| Allow GitHub Actions to create and approve pull requests | Disabled |

## Failure Symptoms

| Symptom | Cause | Fix |
|---------|-------|-----|
| `fatal: not a git repository` | Wrong directory | `cd /path/to/VCW` |
| `fatal: remote origin already exists` | Remote configured | `git remote set-url origin ...` |
| `Permission denied` | No SSH key | Add SSH key to GitHub: `Settings → SSH and GPG keys` |
| `Repository not found` | Wrong URL | Verify username and repo name |

## Troubleshooting

```bash
# Verify remote
git remote -v

# Test SSH connectivity
ssh -T git@github.com

# Force push if initial push fails (first time only)
git push -u origin main --force-with-lease
```
