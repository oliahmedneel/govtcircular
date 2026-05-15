#!/bin/bash
# Fix deployment by properly pushing to GitHub
# Run from D:/JobSite

set -e

echo "=== Fixing Deployment ==="

# 1. Remove the nested .git folder using Python (more reliable)
python -c "
import os, stat, shutil

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

path = r'hugo-site\.git'
if os.path.exists(path):
    shutil.rmtree(path, onerror=remove_readonly)
    print('Removed nested .git folder')
else:
    print('No nested .git folder found')
"

# 2. Remove hugo-site from git staging (if stuck as submodule)
git rm --cached -f hugo-site 2>/dev/null || true

# 3. Add everything
git add -A

# 4. Commit
git commit -m "🚀 Complete project with Hugo site structure"