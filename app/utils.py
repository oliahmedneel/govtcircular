# ========================================
# JobSite — Shared Utility Functions
# ========================================
"""
Common helper functions used across all modules:
- Configuration loading
- Path resolution
- File handling utilities
"""

import os
import hashlib
import yaml
from dotenv import load_dotenv
from datetime import datetime


def load_config(config_path: str | None = None) -> dict:
    """
    Load configuration from YAML file and merge with environment variables.

    Args:
        config_path: Path to settings.yaml. Auto-detected if None.

    Returns:
        Merged configuration dictionary.
    """
    # Load .env file for secrets (API keys, etc.)
    base_dir = get_project_root()
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)

    # Determine config file path
    if config_path is None:
        config_path = os.path.join(base_dir, "config", "settings.yaml")

    # Load YAML config
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Inject environment variables into config
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        config.setdefault("ai", {})["api_key"] = gemini_key

    return config


def get_project_root() -> str:
    """
    Get the absolute path to the project root directory.
    Assumes this file is at <project_root>/app/utils.py.

    Returns:
        Absolute path to project root.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_path(relative_path: str, base_dir: str | None = None) -> str:
    """
    Resolve a relative path against the project root.

    Args:
        relative_path: Path relative to project root.
        base_dir: Optional base directory (defaults to project root).

    Returns:
        Absolute path.
    """
    if os.path.isabs(relative_path):
        return relative_path
    if base_dir is None:
        base_dir = get_project_root()
    return os.path.join(base_dir, relative_path)


def ensure_directories(config: dict) -> None:
    """
    Create all required directories specified in config if they don't exist.

    Args:
        config: Configuration dictionary with 'paths' key.
    """
    paths_cfg = config.get("paths", {})
    base_dir = get_project_root()
    for key, rel_path in paths_cfg.items():
        full_path = os.path.join(base_dir, rel_path)
        os.makedirs(full_path, exist_ok=True)


def compute_file_hash(filepath: str) -> str:
    """
    Compute SHA-256 hash of a file for duplicate detection.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Hex digest of the file's SHA-256 hash.
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_text_hash(text: str) -> str:
    """
    Compute SHA-256 hash of text content for duplicate detection.

    Args:
        text: Text string to hash.

    Returns:
        Hex digest of the text's SHA-256 hash.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_timestamp() -> str:
    """Get current ISO-format timestamp."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+06:00")


def get_date_slug() -> str:
    """Get current date as YYYY-MM-DD for file naming."""
    return datetime.now().strftime("%Y-%m-%d")


def safe_filename(name: str) -> str:
    """
    Convert a string into a safe filename by removing special characters.

    Args:
        name: Original filename string.

    Returns:
        Sanitized filename string.
    """
    # Remove characters that are invalid in Windows filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "")
    # Replace spaces with hyphens
    name = name.strip().replace(" ", "-")
    # Remove consecutive hyphens
    while "--" in name:
        name = name.replace("--", "-")
    return name


def get_supported_extensions(config: dict) -> list[str]:
    """
    Get list of supported file extensions from config.

    Args:
        config: Configuration dictionary.

    Returns:
        List of supported file extensions (e.g., ['.jpg', '.png']).
    """
    return config.get("image", {}).get(
        "supported_extensions",
        [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf", ".webp"],
    )
