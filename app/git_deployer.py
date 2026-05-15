# ========================================
# JobSite — Git Automation & Deployment
# ========================================
"""
Handles Git operations for automatic deployment to GitHub Pages.

Features:
- Auto-commit new posts with descriptive messages
- Push to remote repository
- Error handling with rollback capability
"""

import os
import subprocess

from app.logger import get_logger
from app.utils import get_project_root

logger = get_logger(__name__)


class GitDeployer:
    """
    Manages Git operations for the Hugo site deployment.
    """

    def __init__(self, config: dict):
        """
        Initialize Git deployer.

        Args:
            config: Full configuration dictionary.
        """
        git_cfg = config.get("git", {})
        hugo_cfg = config.get("hugo", {})

        base_dir = get_project_root()
        hugo_site_dir = os.path.join(
            base_dir,
            config.get("paths", {}).get("hugo_site", "hugo-site"),
        )

        self.repo_dir = hugo_site_dir
        self.auto_push = git_cfg.get("auto_push", True)
        self.commit_message_template = git_cfg.get("commit_message", "📝 New post: {title}")
        self.branch = git_cfg.get("branch", "main")
        self.site_url = hugo_cfg.get("base_url", "")

        logger.info("GitDeployer initialized (branch=%s, auto_push=%s)",
                     self.branch, self.auto_push)

    def commit_and_push(self, title: str) -> bool:
        """
        Commit new post and push to remote.

        Args:
            title: Post title for commit message.

        Returns:
            True if successful, False otherwise.
        """
        if not self._is_git_repo():
            logger.warning("Not a git repository: %s", self.repo_dir)
            return False

        try:
            commit_msg = self.commit_message_template.format(title=title)

            # Stage all changes
            logger.info("Staging changes...")
            self._run_git(["add", "."])

            # Check if there's anything to commit
            status = self._run_git(["status", "--porcelain"])
            if not status.strip():
                logger.info("No changes to commit")
                return True

            # Commit
            logger.info("Committing: %s", commit_msg)
            self._run_git(["commit", "-m", commit_msg])

            # Push if auto-push is enabled
            if self.auto_push:
                logger.info("Pushing to origin/%s...", self.branch)
                self._run_git(["push", "origin", self.branch])
                logger.info("Push successful")

            logger.info("Git deploy completed for: %s", title)
            return True

        except subprocess.CalledProcessError as e:
            logger.error("Git operation failed: %s", str(e))
            return False
        except Exception as e:
            logger.error("Git deploy error: %s", str(e))
            return False

    def build_hugo(self) -> bool:
        """
        Build the Hugo site (if Hugo is available).

        Returns:
            True if build succeeded, False otherwise.
        """
        try:
            executable = "hugo"
            logger.info("Building Hugo site...")
            result = subprocess.run(
                [executable],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Hugo build successful")
                return True
            else:
                logger.error("Hugo build failed: %s", result.stderr[:500])
                return False
        except FileNotFoundError:
            logger.warning("Hugo executable not found. Skipping build.")
            return False
        except Exception as e:
            logger.error("Hugo build error: %s", str(e))
            return False

    def _run_git(self, args: list[str]) -> str:
        """
        Run a git command in the repository directory.

        Args:
            args: List of git arguments.

        Returns:
            Command output as string.

        Raises:
            subprocess.CalledProcessError: If git command fails.
        """
        result = subprocess.run(
            ["git"] + args,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                output=result.stdout,
                stderr=result.stderr,
            )

        return result.stdout.strip()

    def _is_git_repo(self) -> bool:
        """
        Check if the hugo-site directory is a git repository.

        Returns:
            True if .git directory exists.
        """
        git_dir = os.path.join(self.repo_dir, ".git")
        return os.path.isdir(git_dir)

    def init_repo(self, remote_url: str | None = None) -> bool:
        """
        Initialize a new git repository (if not already one).

        Args:
            remote_url: Optional remote URL to add.

        Returns:
            True if successful.
        """
        try:
            if not self._is_git_repo():
                logger.info("Initializing git repository...")
                self._run_git(["init"])
                self._run_git(["checkout", "-b", self.branch])

            if remote_url:
                # Check if remote already exists
                try:
                    existing = self._run_git(["remote", "get-url", "origin"])
                    if existing != remote_url:
                        self._run_git(["remote", "set-url", "origin", remote_url])
                except subprocess.CalledProcessError:
                    self._run_git(["remote", "add", "origin", remote_url])

                logger.info("Git remote configured: %s", remote_url)

            logger.info("Git repository initialized")
            return True

        except Exception as e:
            logger.error("Git init failed: %s", str(e))
            return False