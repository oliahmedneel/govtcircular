"""
Deployment Fix Script
Handles the complete deployment process for github pages.
"""
import os
import shutil
import subprocess
import sys

def main():
    print("=" * 60)
    print("DEPLOYMENT FIX SCRIPT")
    print("=" * 60)
    
    # Step 1: Copy hugo-site files to root for deployment
    # The remote repo has files at root level, but local has them in hugo-site/
    print("\n[1/6] Copying Hugo files to root for deployment...")
    
    src = "hugo-site"
    copy_pairs = [
        ("config.toml", "config.toml"),
    ]
    
    for rel_src, rel_dst in copy_pairs:
        src_path = os.path.join(src, rel_src)
        dst_path = rel_dst
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            print(f"  Copied: {rel_src} -> {rel_dst}")
    
    # Copy directories
    dirs_to_copy = ["content", "layouts", "static"]
    for d in dirs_to_copy:
        src_dir = os.path.join(src, d)
        dst_dir = d
        if os.path.exists(src_dir):
            if os.path.exists(dst_dir):
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)
            print(f"  Copied directory: {d}/")
    
    print("  Done copying files")
    
    # Step 2: Remove the nested .git reference from git index
    print("\n[2/6] Removing submodule reference...")
    subprocess.run(["git", "rm", "--cached", "-f", "hugo-site"], 
                   capture_output=True, shell=True)
    
    # Step 3: Update .gitignore to ignore nested git
    print("\n[3/6] Updating .gitignore...")
    with open(".gitignore", "a") as f:
        f.write("\n# Hugo nested git\nhugo-site/.git/\n")
    
    # Step 4: Add everything to git
    print("\n[4/6] Adding files to git...")
    result = subprocess.run(["git", "add", "-A"], capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"  Warning: {result.stderr[:200]}")
    else:
        print("  Files added")
    
    # Step 5: Show status
    print("\n[5/6] Current git status:")
    subprocess.run(["git", "status", "--short"], shell=True)
    
    # Step 6: Instructions for next steps
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
1. Review the status above - make sure hugo-site files are tracked
2. Run these commands:
   git remote add origin https://github.com/oliahmedneel/govtcircular.git
   git commit -m "🚀 Complete project with proper structure"
   git push -f origin main
3. Go to https://github.com/oliahmedneel/govtcircular/actions
   to check if the deployment workflow runs
4. Visit https://oliahmedneel.github.io/govtcircular/
   after deployment completes (usually 2-3 minutes)
""")

if __name__ == "__main__":
    main()