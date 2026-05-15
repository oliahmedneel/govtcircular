# ========================================
# JobSite — SQLite Database Module
# ========================================
"""
Manages SQLite database for:
- Duplicate file detection (hash-based + fuzzy text matching)
- Processing history and status tracking
- Similar post discovery
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime

from app.logger import get_logger
from app.utils import (
    get_project_root,
    compute_file_hash,
    compute_text_hash,
    get_timestamp,
)

logger = get_logger(__name__)


class Database:
    """
    SQLite database manager for duplicate detection and history tracking.
    """

    def __init__(self, config: dict):
        """
        Initialize database connection.

        Args:
            config: Full configuration dictionary.
        """
        data_dir = os.path.join(
            get_project_root(),
            config.get("paths", {}).get("data", "data"),
        )
        os.makedirs(data_dir, exist_ok=True)

        self.db_path = os.path.join(data_dir, "jobsite.db")
        self.similarity_threshold = config.get("duplicate", {}).get("similarity_threshold", 85)
        self.hash_check_enabled = config.get("duplicate", {}).get("hash_check", True)
        self.title_check_enabled = config.get("duplicate", {}).get("title_check", True)

        self.conn = None
        self.initialize()

        logger.info("Database initialized: %s", self.db_path)

    def initialize(self) -> None:
        """Create database tables if they don't exist."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA busy_timeout=5000")
            self.conn.execute("PRAGMA synchronous=OFF")

            cursor = self.conn.cursor()

            # Files table — tracks all processed files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    file_hash TEXT,
                    text_hash TEXT,
                    category TEXT,
                    slug TEXT,
                    status TEXT DEFAULT 'pending',
                    error TEXT,
                    processed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Hash index for fast duplicate lookup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash
                ON files(file_hash)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_text_hash
                ON files(text_hash)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON files(status)
            """)

            # Posts table — tracks generated Hugo posts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT,
                    category TEXT,
                    file_id INTEGER REFERENCES files(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_slug
                ON posts(slug)
            """)

            self.conn.commit()
            logger.debug("Database tables verified/created")

        except sqlite3.Error as e:
            logger.error("Database initialization failed: %s", str(e))
            raise

    def check_duplicate(self, filepath: str) -> dict:
        """
        Check if a file is a duplicate based on hash or text similarity.

        Args:
            filepath: Absolute path to the file.

        Returns:
            Dict with 'is_duplicate', 'method', 'matched_file' keys.
        """
        result = {"is_duplicate": False, "method": None, "matched_file": None}

        if not self.hash_check_enabled and not self.title_check_enabled:
            return result

        cursor = self.conn.cursor()

        # 1. Hash-based check (fast, exact)
        if self.hash_check_enabled:
            try:
                file_hash = compute_file_hash(filepath)
                cursor.execute(
                    "SELECT filepath FROM files WHERE file_hash = ? AND status = 'success'",
                    (file_hash,),
                )
                row = cursor.fetchone()
                if row:
                    result["is_duplicate"] = True
                    result["method"] = "hash"
                    result["matched_file"] = row[0]
                    logger.info("Hash duplicate: %s", row[0])
                    return result
            except Exception as e:
                logger.warning("Hash check failed: %s", str(e))

        return result

    def find_similar(self, filepath: str, ocr_text: str) -> str | None:
        """
        Find similar previously processed content using text hash.

        Args:
            filepath: Path to current file.
            ocr_text: OCR-extracted text for comparison.

        Returns:
            Slug of similar post if found, else None.
        """
        if not self.title_check_enabled or not ocr_text:
            return None

        try:
            text_hash = compute_text_hash(ocr_text[:500])
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT slug FROM files WHERE text_hash = ? AND status = 'success'",
                (text_hash,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

        except Exception as e:
            logger.warning("Similarity check failed: %s", str(e))
            return None

    def record_file(
        self,
        filepath: str,
        category: str | None,
        slug: str | None,
        status: str = "success",
        error: str | None = None,
    ) -> int:
        """
        Record a processed file in the database.

        Args:
            filepath: Absolute path to the file.
            category: Classification category.
            slug: Generated post slug.
            status: Processing status (success/failed).
            error: Error message if failed.

        Returns:
            Row ID of the inserted record.
        """
        try:
            file_hash = compute_file_hash(filepath)
            text_hash = None
            if slug:
                text_hash = compute_text_hash(slug)

            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO files
                   (filename, filepath, file_hash, text_hash, category, slug, status, error, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    os.path.basename(filepath),
                    filepath,
                    file_hash,
                    text_hash,
                    category,
                    slug,
                    status,
                    error,
                    get_timestamp(),
                ),
            )

            file_id = cursor.lastrowid

            # Also record in posts table if successful
            if status == "success" and slug:
                cursor.execute(
                    """INSERT OR IGNORE INTO posts
                       (slug, title, category, file_id)
                       VALUES (?, ?, ?, ?)""",
                    (slug, os.path.basename(filepath), category, file_id),
                )

            self.conn.commit()
            logger.debug("Recorded file: %s (status=%s)", os.path.basename(filepath), status)
            return file_id

        except sqlite3.Error as e:
            logger.error("Failed to record file: %s", str(e))
            return -1

    def get_stats(self) -> dict:
        """
        Get processing statistics from the database.

        Returns:
            Dict with counts of processed files by status and category.
        """
        cursor = self.conn.cursor()
        stats = {}

        # Total counts by status
        cursor.execute(
            "SELECT status, COUNT(*) FROM files GROUP BY status"
        )
        stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Total counts by category
        cursor.execute(
            "SELECT category, COUNT(*) FROM files WHERE status='success' GROUP BY category"
        )
        stats["by_category"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Total posts
        cursor.execute("SELECT COUNT(*) FROM posts")
        stats["total_posts"] = cursor.fetchone()[0]

        # Recent files
        cursor.execute(
            "SELECT filename, category, slug, processed_at FROM files "
            "ORDER BY processed_at DESC LIMIT 10"
        )
        stats["recent"] = [
            {
                "filename": row[0],
                "category": row[1],
                "slug": row[2],
                "processed_at": row[3],
            }
            for row in cursor.fetchall()
        ]

        return stats

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")