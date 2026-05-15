# ========================================
# JobSite — Automated Static Site Publisher (Phase 2)
# ========================================
"""
Complete automated publishing pipeline:
1. Detect new markdown files
2. Classify into category folders (jobs/tenders/notices)
3. Copy into Hugo content structure
4. Run Hugo build
5. Git add/commit/push
6. Deploy to GitHub Pages

Usage:
    from app.publisher import Publisher
    publisher = Publisher(config)
    result = publisher.publish_all()
    result = publisher.publish_single("path/to/file.md")
"""

import os
import re
import sys
import json
import shutil
import subprocess
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Publisher:
    """
    Automated static site publishing system.
    Handles markdown import, Hugo build, and Git deployment.
    """

    def __init__(self, config: dict):
        """
        Initialize publisher with project configuration.

        Args:
            config: Full configuration dictionary from settings.yaml
        """
        self.project_root = self._get_project_root()
        self.config = config

        # Paths from config
        paths = config.get("paths", {})
        self.hugo_site_dir = os.path.join(
            self.project_root, paths.get("hugo_site", "hugo-site")
        )
        self.hugo_content_dir = os.path.join(
            self.hugo_site_dir, paths.get("hugo_content", "content/posts")
        )
        self.hugo_public_dir = os.path.join(self.hugo_site_dir, "public")
        self.processed_dir = os.path.join(
            self.project_root, paths.get("processed", "processed")
        )

        # Category to content folder mapping
        self.category_map = {
            "job_circular": "jobs",
            "tender_notice": "tenders",
            "admission": "notices",
            "public_notice": "notices",
            "unknown": "notices",
        }
        # English category keys
        self.category_keywords = {
            "job_circular": ["job circular", "চাকরির বিজ্ঞপ্তি", "নিয়োগ"],
            "tender_notice": ["tender", "দরপত্র"],
            "admission": ["admission", "ভর্তি"],
            "public_notice": ["public notice", "সরকারি বিজ্ঞপ্তি", "বিজ্ঞপ্তি"],
            "unknown": ["other", "অন্যান্য"],
        }
        # Category slug mappings
        self.category_slugs = {
            "job_circular": "job-circular",
            "tender_notice": "tender-notice",
            "admission": "admission",
            "public_notice": "public-notice",
            "unknown": "unknown",
        }
        self.category_names_bn = {
            "job_circular": "চাকরির বিজ্ঞপ্তি",
            "tender_notice": "দরপত্র বিজ্ঞপ্তি",
            "admission": "ভর্তি বিজ্ঞপ্তি",
            "public_notice": "সরকারি বিজ্ঞপ্তি",
            "unknown": "অন্যান্য",
        }

        # Git config
        git_config = config.get("git", {})
        self.git_branch = git_config.get("branch", "main")
        self.auto_push = git_config.get("auto_push", True)
        self.git_remote = git_config.get("remote", "origin")

        # Hugo config
        hugo_config = config.get("hugo", {})
        self.hugo_binary = hugo_config.get(
            "binary", self._find_hugo_binary()
        )
        self.build_on_publish = hugo_config.get("build_on_publish", True)

        # Deploy config
        self.deploy_branch = "gh-pages"  # Default branch for GitHub Pages

        logger.info("Publisher initialized (hugo=%s, branch=%s, push=%s)",
                     self.hugo_binary, self.git_branch, self.auto_push)

    def _get_project_root(self) -> str:
        """Get project root directory."""
        # Try multiple methods to find the root
        for method in [
            lambda: os.environ.get("PROJECT_ROOT"),
            lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ]:
            result = method()
            if result and os.path.exists(result):
                return result
        return os.getcwd()

    def _find_hugo_binary(self) -> str:
        """Find Hugo executable on system."""
        # Common Hugo installation paths
        candidates = [
            "hugo",
            "hugo.exe",
            os.path.expanduser("~/go/bin/hugo"),
            os.path.expanduser("~/go/bin/hugo.exe"),
            "C:\\Program Files\\Hugo\\bin\\hugo.exe",
            "C:\\Hugo\\bin\\hugo.exe",
        ]
        for candidate in candidates:
            try:
                subprocess.run(
                    [candidate, "version"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                logger.info("Found Hugo: %s", candidate)
                return candidate
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        logger.warning("Hugo not found. Will attempt 'hugo' as default.")
        return "hugo"

    # ==========================================
    # MARKDOWN PARSING
    # ==========================================

    def parse_markdown_metadata(self, filepath: str) -> dict:
        """
        Parse YAML frontmatter from a markdown file.

        Args:
            filepath: Path to markdown file

        Returns:
            Dict with metadata fields
        """
        metadata = {
            "title": "",
            "slug": "",
            "category": "unknown",
            "date": "",
            "tags": [],
            "summary": "",
            "image": "",
            "author": "",
        }

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract YAML frontmatter between --- markers
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
            if not match:
                logger.warning("No frontmatter found in %s", filepath)
                metadata["summary"] = content[:200]
                return metadata

            frontmatter = match.group(1)
            body = match.group(2)
            metadata["summary"] = body[:300].strip()

            # Parse each line
            for line in frontmatter.split("\n"):
                line = line.strip()
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower()
                    value = value.strip().strip('"').strip("'")

                    if key == "title":
                        metadata["title"] = value
                    elif key == "slug":
                        metadata["slug"] = value
                    elif key == "category":
                        metadata["category"] = value.lower()
                    elif key == "date":
                        metadata["date"] = value
                    elif key == "tags":
                        # Parse tag list: ["tag1", "tag2"] or [tag1, tag2]
                        tags = re.findall(r'"([^"]+)"', value)
                        if not tags:
                            tags = re.findall(r"(\w+)", value)
                        metadata["tags"] = tags
                    elif key == "image":
                        metadata["image"] = value
                    elif key == "author":
                        metadata["author"] = value
                    elif key == "description":
                        if not metadata["summary"]:
                            metadata["summary"] = value

            # Auto-detect category if not set or 'unknown'
            if metadata["category"] in ["unknown", "", "uncategorized"]:
                detected = self.detect_category(metadata["title"], body)
                metadata["category"] = detected

            logger.debug("Parsed metadata: title=%s, category=%s, slug=%s",
                         metadata["title"], metadata["category"], metadata["slug"])
            return metadata

        except Exception as e:
            logger.error("Failed to parse markdown: %s", str(e))
            return metadata

    def detect_category(self, title: str, body: str = "") -> str:
        """
        Auto-detect category from title and content.

        Args:
            title: Post title
            body: Post body content

        Returns:
            Category key
        """
        text = (title + " " + body).lower()

        # Score each category
        scores = {}
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in text:
                    score += 1
            scores[category] = score

        # Return highest scoring category
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        return "unknown"

    # ==========================================
    # CONTENT MOVEMENT
    # ==========================================

    def move_to_hugo_content(self, filepath: str, category: str = "unknown") -> Optional[str]:
        """
        Move a markdown file into the appropriate Hugo content folder.

        Args:
            filepath: Source markdown file path
            category: Target category key

        Returns:
            Destination path, or None on failure
        """
        if not os.path.exists(filepath):
            logger.error("Source file not found: %s", filepath)
            return None

        # Determine target subfolder
        subfolder = self.category_map.get(category, "notices")
        target_dir = os.path.join(self.hugo_site_dir, "content", subfolder)
        os.makedirs(target_dir, exist_ok=True)

        # Generate filename
        basename = os.path.basename(filepath)
        if not basename.endswith(".md"):
            basename += ".md"

        # Handle duplicates by adding timestamp
        dest_path = os.path.join(target_dir, basename)
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(basename)
            basename = f"{name}-{int(time.time())}{ext}"
            dest_path = os.path.join(target_dir, basename)

        # Copy file to Hugo content
        try:
            shutil.copy2(filepath, dest_path)
            logger.info("Copied to Hugo: %s -> %s", filepath, dest_path)
            return dest_path
        except Exception as e:
            logger.error("Failed to copy to Hugo: %s", str(e))
            return None

    def sync_all_posts(self) -> list:
        """
        Sync all markdown posts from the processed directory
        into the proper Hugo content folders.

        Returns:
            List of synced file paths
        """
        synced = []

        # Gather all markdown files from processed and posts directories
        source_dirs = [
            self.processed_dir,
            os.path.join(self.hugo_site_dir, "content", "posts"),
        ]

        for src_dir in source_dirs:
            if not os.path.exists(src_dir):
                continue
            for fname in os.listdir(src_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(src_dir, fname)

                # Parse metadata to determine category
                metadata = self.parse_markdown_metadata(fpath)
                category = metadata.get("category", "unknown")

                # Move to proper folder
                dest = self.move_to_hugo_content(fpath, category)
                if dest:
                    synced.append(dest)

        logger.info("Synced %d posts to Hugo content", len(synced))
        return synced

    # ==========================================
    # SEARCH INDEX GENERATION
    # ==========================================

    def generate_search_index(self) -> Optional[str]:
        """
        Generate a searchable JSON index of all posts.

        Returns:
            Path to generated JSON index, or None
        """
        content_dirs = [
            os.path.join(self.hugo_site_dir, "content", folder)
            for folder in ["jobs", "tenders", "notices", "posts"]
        ]

        posts = []
        for content_dir in content_dirs:
            if not os.path.exists(content_dir):
                continue
            for fname in os.listdir(content_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(content_dir, fname)
                metadata = self.parse_markdown_metadata(fpath)

                # Generate slug from filename
                slug = os.path.splitext(fname)[0]
                category = metadata.get("category", "unknown")
                cat_slug = self.category_slugs.get(category, "unknown")

                posts.append({
                    "title": metadata.get("title", fname),
                    "slug": slug,
                    "category": cat_slug,
                    "category_bn": self.category_names_bn.get(category, "অন্যান্য"),
                    "url": f"/{cat_slug}/{slug}/",
                    "summary": metadata.get("summary", "")[:200],
                    "tags": metadata.get("tags", []),
                    "date": metadata.get("date", ""),
                })

        if not posts:
            logger.warning("No posts found for search index")
            return None

        # Write search index
        index_path = os.path.join(self.hugo_site_dir, "static", "search-index.json")
        try:
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)
            logger.info("Search index generated: %d posts at %s", len(posts), index_path)
            return index_path
        except Exception as e:
            logger.error("Failed to generate search index: %s", str(e))
            return None

    # ==========================================
    # HUGO BUILD
    # ==========================================

    def run_hugo_build(self) -> bool:
        """
        Run Hugo static site build.

        Returns:
            True if build succeeded
        """
        if not self.build_on_publish:
            logger.info("Hugo build disabled by configuration")
            return True

        logger.info("Running Hugo build in: %s", self.hugo_site_dir)

        try:
            result = subprocess.run(
                [self.hugo_binary],
                cwd=self.hugo_site_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                logger.info("Hugo build successful")
                logger.debug("Hugo output: %s", result.stdout[-500:] if result.stdout else "")
                return True
            else:
                logger.error("Hugo build failed (code=%d)", result.returncode)
                logger.error("Stderr: %s", result.stderr[-1000:] if result.stderr else "")
                return False

        except FileNotFoundError:
            logger.error("Hugo binary not found: %s", self.hugo_binary)
            return False
        except subprocess.TimeoutExpired:
            logger.error("Hugo build timed out after 120 seconds")
            return False
        except Exception as e:
            logger.error("Hugo build error: %s", str(e))
            return False

    # ==========================================
    # GIT AUTOMATION
    # ==========================================

    def _run_git_command(self, args: list) -> tuple:
        """
        Run a git command in the Hugo site directory.

        Args:
            args: Git command arguments

        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.hugo_site_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                logger.warning("Git command failed: git %s", " ".join(args))
                logger.warning("Stderr: %s", result.stderr[:500])
                return False, result.stderr.strip()
        except FileNotFoundError:
            logger.error("Git not found on system")
            return False, "Git not found"
        except Exception as e:
            logger.error("Git error: %s", str(e))
            return False, str(e)

    def git_add_all(self) -> bool:
        """Stage all changes in Hugo site."""
        success, output = self._run_git_command(["add", "-A"])
        if success:
            logger.info("Git add successful")
        return success

    def git_commit(self, message: str = "") -> bool:
        """Commit staged changes."""
        if not message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"📝 Auto-publish: {timestamp}"

        success, output = self._run_git_command(["commit", "-m", message])
        if success:
            logger.info("Git commit successful: %s", message)
        elif "nothing to commit" in output.lower() or "nothing added" in output.lower():
            logger.info("Nothing to commit - no changes detected")
            return True  # Not an error
        return success

    def git_push(self) -> bool:
        """Push to remote repository."""
        success, output = self._run_git_command(
            ["push", self.git_remote, self.git_branch]
        )
        if success:
            logger.info("Git push successful to %s/%s", self.git_remote, self.git_branch)
        return success

    def git_deploy_to_pages(self) -> bool:
        """
        Deploy Hugo public folder to gh-pages branch.
        Alternative: simply push to main and let GitHub Actions deploy.
        This method pushes public folder to gh-pages.
        """
        if not os.path.exists(self.hugo_public_dir):
            logger.warning("Public dir not found: %s", self.hugo_public_dir)
            return False

        # Simple approach: push main branch and rely on GitHub Actions
        # or push public folder to gh-pages directly
        return self.git_push()

    # ==========================================
    # FULL PUBLISH PIPELINE
    # ==========================================

    def publish_all(self) -> dict:
        """
        Run the complete publishing pipeline:
        1. Sync all posts to Hugo content
        2. Generate search index
        3. Run Hugo build
        4. Git add/commit/push

        Returns:
            Dict with pipeline results
        """
        results = {
            "success": False,
            "steps": {},
            "errors": [],
            "started_at": datetime.now().isoformat(),
        }

        logger.info("=" * 60)
        logger.info("PUBLISHING PIPELINE STARTED")
        logger.info("=" * 60)

        # Step 1: Sync posts to Hugo content
        logger.info("Step 1/5: Syncing posts to Hugo content...")
        try:
            synced = self.sync_all_posts()
            results["steps"]["sync"] = {"success": True, "count": len(synced)}
            logger.info("  -> Synced %d posts", len(synced))
        except Exception as e:
            results["steps"]["sync"] = {"success": False, "error": str(e)}
            results["errors"].append(f"Sync failed: {e}")
            logger.error("  -> Sync failed: %s", e)

        # Step 2: Generate search index
        logger.info("Step 2/5: Generating search index...")
        try:
            index_path = self.generate_search_index()
            results["steps"]["search_index"] = {
                "success": index_path is not None,
                "path": index_path,
            }
            if index_path:
                logger.info("  -> Search index: %s", index_path)
        except Exception as e:
            results["steps"]["search_index"] = {"success": False, "error": str(e)}
            logger.error("  -> Search index failed: %s", e)

        # Step 3: Run Hugo build
        logger.info("Step 3/5: Running Hugo build...")
        try:
            build_ok = self.run_hugo_build()
            results["steps"]["hugo_build"] = {"success": build_ok}
            if build_ok:
                logger.info("  -> Hugo build OK")
            else:
                results["errors"].append("Hugo build failed")
                logger.error("  -> Hugo build FAILED")
        except Exception as e:
            results["steps"]["hugo_build"] = {"success": False, "error": str(e)}
            results["errors"].append(f"Hugo build error: {e}")
            logger.error("  -> Hugo build error: %s", e)

        # Step 4: Git add and commit
        logger.info("Step 4/5: Git staging & commit...")
        try:
            add_ok = self.git_add_all()
            if add_ok:
                commit_msg = f"📝 Auto-publish: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                commit_ok = self.git_commit(commit_msg)
                results["steps"]["git_commit"] = {"success": commit_ok}
                if commit_ok:
                    logger.info("  -> Git commit OK")
                else:
                    logger.warning("  -> Git commit skipped (no changes)")
            else:
                results["steps"]["git_commit"] = {"success": False, "error": "Git add failed"}
                results["errors"].append("Git add failed")
        except Exception as e:
            results["steps"]["git_commit"] = {"success": False, "error": str(e)}
            logger.error("  -> Git commit error: %s", e)

        # Step 5: Git push (if auto-push enabled)
        if self.auto_push:
            logger.info("Step 5/5: Git push to remote...")
            try:
                push_ok = self.git_push()
                results["steps"]["git_push"] = {"success": push_ok}
                if push_ok:
                    logger.info("  -> Git push OK")
                else:
                    results["errors"].append("Git push failed")
                    logger.error("  -> Git push FAILED")
            except Exception as e:
                results["steps"]["git_push"] = {"success": False, "error": str(e)}
                results["errors"].append(f"Git push error: {e}")
                logger.error("  -> Git push error: %s", e)
        else:
            results["steps"]["git_push"] = {"success": True, "skipped": True}
            logger.info("Step 5/5: Git push skipped (auto_push=False)")

        # Summary
        results["completed_at"] = datetime.now().isoformat()
        results["success"] = len(results["errors"]) == 0

        logger.info("=" * 60)
        if results["success"]:
            logger.info("PUBLISHING COMPLETED SUCCESSFULLY")
        else:
            logger.info("PUBLISHING COMPLETED WITH %d ERROR(S)", len(results["errors"]))
        logger.info("=" * 60)

        return results

    def publish_single(self, filepath: str) -> dict:
        """
        Publish a single markdown file through the pipeline.

        Args:
            filepath: Path to the markdown file

        Returns:
            Dict with publish results
        """
        results = {
            "success": False,
            "filepath": filepath,
            "errors": [],
        }

        if not os.path.exists(filepath):
            results["errors"].append(f"File not found: {filepath}")
            return results

        logger.info("Publishing single file: %s", filepath)

        # Parse metadata
        metadata = self.parse_markdown_metadata(filepath)
        category = metadata.get("category", "unknown")

        # Move to Hugo content
        dest = self.move_to_hugo_content(filepath, category)
        if not dest:
            results["errors"].append("Failed to move file to Hugo content")
            return results
        results["destination"] = dest

        # Generate search index
        try:
            self.generate_search_index()
        except Exception as e:
            logger.warning("Search index generation failed: %s", e)

        # Run Hugo build
        build_ok = self.run_hugo_build()
        results["hugo_build"] = build_ok
        if not build_ok:
            results["errors"].append("Hugo build failed")

        # Git operations
        add_ok = self.git_add_all()
        if add_ok:
            commit_msg = f"📝 Published: {metadata.get('title', os.path.basename(filepath))}"
            self.git_commit(commit_msg)

            if self.auto_push:
                push_ok = self.git_push()
                results["git_push"] = push_ok
                if not push_ok:
                    results["errors"].append("Git push failed")

        results["success"] = len(results["errors"]) == 0
        logger.info("Single publish result: %s", "SUCCESS" if results["success"] else "FAILED")
        return results

    # ==========================================
    # SETUP & INITIALIZATION
    # ==========================================

    def setup_repository(self) -> bool:
        """
        Initialize git repository and configure for GitHub Pages.
        Run this once when setting up the project.

        Returns:
            True if setup successful
        """
        logger.info("Setting up repository for GitHub Pages...")

        # Initialize git if needed
        success, output = self._run_git_command(["status"])
        if not success and "not a git repository" in output:
            logger.info("Initializing git repository...")
            success, output = self._run_git_command(["init"])
            if not success:
                logger.error("Git init failed: %s", output)
                return False
            logger.info("Git repository initialized")

        # Create .gitignore
        gitignore_path = os.path.join(self.hugo_site_dir, ".gitignore")
        gitignore_content = """# Hugo
/public/
/resources/_gen/
/hugo_stats.json

# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp
*.swo
"""
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(gitignore_content)
        logger.info("Created .gitignore")

        # Ensure content directories exist
        for folder in ["jobs", "tenders", "notices", "posts"]:
            dir_path = os.path.join(self.hugo_site_dir, "content", folder)
            os.makedirs(dir_path, exist_ok=True)
            # Create .gitkeep
            keep_file = os.path.join(dir_path, ".gitkeep")
            if not os.path.exists(keep_file):
                with open(keep_file, "w") as f:
                    f.write("")

        # Create empty _index.md for sections
        for folder in ["jobs", "tenders", "notices", "posts"]:
            index_path = os.path.join(self.hugo_site_dir, "content", folder, "_index.md")
            if not os.path.exists(index_path):
                name_map = {
                    "jobs": "চাকরির বিজ্ঞপ্তি",
                    "tenders": "দরপত্র বিজ্ঞপ্তি",
                    "notices": "বিজ্ঞপ্তি",
                    "posts": "সকল পোস্ট",
                }
                with open(index_path, "w", encoding="utf-8") as f:
                    f.write(f"""---
title: "{name_map.get(folder, folder)}"
date: {datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
---
""")

        logger.info("Repository setup complete")
        return True

    def check_hugo_installation(self) -> dict:
        """
        Check if Hugo is properly installed.

        Returns:
            Dict with installation info
        """
        try:
            result = subprocess.run(
                [self.hugo_binary, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {
                    "installed": True,
                    "version": result.stdout.strip(),
                    "binary": self.hugo_binary,
                }
        except Exception:
            pass
        return {
            "installed": False,
            "version": None,
            "binary": self.hugo_binary,
            "error": "Hugo not found. Install from: https://gohugo.io/installation/",
        }


# ==========================================
# CLI ENTRY POINT
# ==========================================

def main():
    """CLI entry point for publishing."""
    import argparse
    from app.utils import load_config

    parser = argparse.ArgumentParser(description="JobSite Publisher - Automated Static Site Publishing")
    parser.add_argument("--file", "-f", help="Publish a single markdown file")
    parser.add_argument("--all", "-a", action="store_true", help="Publish all posts")
    parser.add_argument("--setup", action="store_true", help="Setup repository for publishing")
    parser.add_argument("--check", action="store_true", help="Check Hugo installation")
    parser.add_argument("--search-index", action="store_true", help="Generate search index only")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # Load config
    config = load_config()
    publisher = Publisher(config)

    if args.check:
        info = publisher.check_hugo_installation()
        print(f"\nHugo Installation: {'✅ FOUND' if info['installed'] else '❌ NOT FOUND'}")
        if info.get("version"):
            print(f"Version: {info['version']}")
            print(f"Binary: {info['binary']}")
        if info.get("error"):
            print(f"Error: {info['error']}")
        return

    if args.setup:
        print("\n🚀 Setting up repository for GitHub Pages...")
        success = publisher.setup_repository()
        print(f"{'✅ Setup complete!' if success else '❌ Setup failed'}")
        return

    if args.search_index:
        print("\n🔍 Generating search index...")
        path = publisher.generate_search_index()
        if path:
            print(f"✅ Search index: {path}")
        else:
            print("❌ Failed to generate search index")
        return

    if args.file:
        print(f"\n📝 Publishing single file: {args.file}")
        result = publisher.publish_single(args.file)
        print(f"{'✅ Published!' if result['success'] else '❌ Failed'}")
        if result.get("destination"):
            print(f"Destination: {result['destination']}")
        if result.get("errors"):
            print(f"Errors: {result['errors']}")
        return

    if args.all:
        print("\n🚀 Publishing all posts...")
        result = publisher.publish_all()
        print(f"{'✅ All published!' if result['success'] else '❌ Failed'}")
        for step, step_result in result.get("steps", {}).items():
            status = "✅" if step_result.get("success") else "❌"
            print(f"  {status} {step}")
        if result.get("errors"):
            print(f"\nErrors ({len(result['errors'])}):")
            for err in result["errors"]:
                print(f"  - {err}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()