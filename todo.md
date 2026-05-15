# Bug Fix Plan: Site Not Going Live (গভর্নমেন্ট সার্কুলার সাইট লাইভ হচ্ছে না)

## Root Cause Analysis

**Identified Issues:**

1. **Remote vs Local Structure Mismatch**: The remote repository (`oliahmedneel/govtcircular`) has Hugo files at **root level** (`config.toml`, `content/`, `layouts/`, `static/` directly at repo root). But the local project has everything inside **`hugo-site/`** subdirectory.

2. **3 Competing Workflows on Remote**: The remote repo has 3 GitHub Actions workflows (`hugo-deploy.yml`, `hugo.yml`, `static.yml`) that all try to deploy to GitHub Pages, potentially conflicting with each other.

3. **Workflow Doesn't Match Local Structure**: The remote workflow doesn't have `working-directory: hugo-site`, so when GitHub Actions runs after a push from the local publisher, it can't build correctly.

## Fix Checklist
- [x] Diagnose the issue (remote repo structure vs local structure)
- [ ] Fix: Remove redundant remote workflows (keep only one)
- [ ] Fix: Update workflow to properly reference `hugo-site/` subdirectory
- [ ] Fix: Push updated code to trigger fresh deployment
- [ ] Verify: Site goes live at https://oliahmedneel.github.io/govtcircular/