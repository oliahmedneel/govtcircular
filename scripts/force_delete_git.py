"""
Force delete the nested .git directory in hugo-site
"""
import os
import shutil
import stat

def on_rm_error(func, path, exc_info):
    """Error handler for shutil.rmtree - try to change permissions and retry"""
    # Clear the readonly bit and reattempt
    os.chmod(path, stat.S_IWRITE)
    func(path)

git_dir = os.path.join('hugo-site', '.git')
if os.path.exists(git_dir):
    print(f"Attempting to delete: {git_dir}")
    try:
        # First try to change all files to writable
        for root, dirs, files in os.walk(git_dir):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), stat.S_IWRITE)
                except:
                    pass
            for f in files:
                try:
                    os.chmod(os.path.join(root, f), stat.S_IWRITE)
                except:
                    pass
        
        # Force delete
        shutil.rmtree(git_dir, onerror=on_rm_error, ignore_errors=False)
        print("Delete attempt completed")
    except Exception as e:
        print(f"Error: {e}")

if os.path.exists(git_dir):
    print("FAILED: .git still exists")
else:
    print("SUCCESS: .git deleted")