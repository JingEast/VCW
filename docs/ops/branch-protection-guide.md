# Branch Protection Rules Guide

## Objective
Protect `main` branch from direct pushes and enforce quality gates.

---

## Navigation
`Repository → Settings → Branches → Add rule`

URL: `https://github.com/YOUR_USERNAME/VCW/settings/branches`

---

## Rule: `main`

### Branch Name Pattern
```
main
```

### Protection Settings

| Setting | Value | Reason |
|---------|-------|--------|
| **Require a pull request before merging** | ✅ Enabled | Enforces code review |
| → Require approvals | `1` | At least 1 reviewer |
| → Dismiss stale PR approvals | ✅ Enabled | Re-approve after new commits |
| **Require status checks to pass** | ✅ Enabled | CI must pass |
| → Search for checks | `lint`, `test`, `migration-check`, `docker-smoke` | All CI jobs |
| → Require branches to be up to date | ✅ Enabled | Prevent merge conflicts |
| **Require conversation resolution** | ✅ Enabled | All review comments resolved |
| **Require linear history** | ✅ Enabled | Clean commit history |
| **Require signed commits** | ❌ Disabled | Optional (enable if team uses GPG) |
| **Include administrators** | ✅ Enabled | Rules apply to admins too |
| **Restrict pushes that create files** | ❌ Disabled | Not needed |
| **Allow force pushes** | ❌ Disabled | Prevent history rewrite |
| **Allow deletions** | ❌ Disabled | Prevent accidental deletion |

### Steps
1. Go to `Settings → Branches`
2. Click **Add branch protection rule**
3. Branch name pattern: `main`
4. Enable settings as listed above
5. Under **Status checks**, search and add:
   - `lint`
   - `test`
   - `migration-check`
   - `docker-smoke`
6. Click **Create**

### Rule: `master` (if used)
Repeat the same steps with pattern `master`.

## Failure Symptoms

| Symptom | Cause | Fix |
|---------|-------|-----|
| Direct push to `main` rejected | Branch protection enabled | Create PR instead |
| PR merge button grayed out | Status checks failing | Fix CI failures |
| PR merge blocked | Review required | Request review from team member |
| "This branch is out-of-date" | `Require up-to-date` enabled | Click **Update branch** |

## Troubleshooting

```bash
# If you accidentally push to main directly and get rejected
git checkout -b fix/something
git push origin fix/something
# Then create PR via GitHub UI
```
