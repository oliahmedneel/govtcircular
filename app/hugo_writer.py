# ========================================
# JobSite — Hugo Markdown Post Writer
# ========================================
"""
Creates Hugo-compatible markdown posts with YAML frontmatter.

Generates properly formatted markdown files in the Hugo content directory
with SEO-optimized frontmatter (title, date, tags, categories, etc.)
"""

import os
import json
from datetime import datetime

from app.logger import get_logger
from app.utils import get_project_root

logger = get_logger(__name__)


class HugoWriter:
    """
    Writes AI-generated articles as Hugo markdown posts with YAML frontmatter.
    """

    CATEGORY_MAP = {
        "job_circular": "চাকরি",
        "tender_notice": "দরপত্র",
        "admission": "ভর্তি",
        "public_notice": "বিজ্ঞপ্তি",
        "unknown": "অন্যান্য",
    }

    def __init__(self, config: dict):
        """
        Initialize Hugo writer with path configuration.

        Args:
            config: Full configuration dictionary.
        """
        paths = config.get("paths", {})
        hugo_cfg = config.get("hugo", {})

        base_dir = get_project_root()
        hugo_site_dir = os.path.join(base_dir, paths.get("hugo_site", "hugo-site"))
        self.content_dir = os.path.join(
            hugo_site_dir, paths.get("hugo_content", "content/posts")
        )
        self.images_dir = os.path.join(
            hugo_site_dir, paths.get("hugo_images", "static/images")
        )
        self.site_language = hugo_cfg.get("language", "bn")

        # Ensure content directories exist
        os.makedirs(self.content_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)

        logger.info("HugoWriter initialized (content=%s)", self.content_dir)

    def write_post(self, article: dict, category: str, source_filename: str) -> str:
        """
        Write a Hugo markdown post from an AI-generated article.

        Args:
            article: Dict with seo_title, slug, meta_description, summary, tags, article_body.
            category: Content category key (e.g., 'job_circular').
            source_filename: Original source file name for reference.

        Returns:
            Absolute path to the created markdown file.
        """
        slug = article.get("slug", self._generate_slug(article, category))
        title = article.get("seo_title", "বিজ্ঞপ্তি")
        meta_desc = article.get("meta_description", "")
        summary = article.get("summary", "")
        tags = article.get("tags", [self.CATEGORY_MAP.get(category, "অন্যান্য")])
        article_body = article.get("article_body", "")

        # Ensure slug is safe
        slug = self._safe_slug(slug)

        # Generate YAML frontmatter
        frontmatter = self._generate_frontmatter(
            title=title,
            slug=slug,
            category=category,
            tags=tags,
            meta_description=meta_desc,
            summary=summary,
            source=source_filename,
        )

        # Full markdown content
        markdown_content = f"{frontmatter}\n\n{article_body}\n"

        # Write to file
        post_path = os.path.join(self.content_dir, f"{slug}.md")

        with open(post_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info("Post created: %s", post_path)
        return post_path

    def _generate_frontmatter(
        self,
        title: str,
        slug: str,
        category: str,
        tags: list[str],
        meta_description: str,
        summary: str,
        source: str,
    ) -> str:
        """
        Generate YAML frontmatter for Hugo posts.

        Args:
            title: SEO-optimized title.
            slug: URL slug.
            category: Content category.
            tags: List of tags.
            meta_description: Meta description for SEO.
            summary: Short description for listing pages.
            source: Original source filename.

        Returns:
            YAML frontmatter as a string.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        category_bn = self.CATEGORY_MAP.get(category, "অন্যান্য")

        lines = [
            "---",
            f'title: "{title}"',
            f'date: {today}',
            f'slug: "{slug}"',
            f'description: "{meta_description}"',
            f'summary: "{summary}"',
            f"categories:",
            f"  - {category_bn}",
            f"tags:",
        ]

        for tag in tags:
            lines.append(f"  - {tag}")

        lines.extend([
            f"type: post",
            f"draft: false",
            f"source: \"{source}\"",
            "---",
        ])

        return "\n".join(lines)

    def _safe_slug(self, slug: str) -> str:
        """
        Ensure slug is safe for file systems and URLs.

        Args:
            slug: Original slug string.

        Returns:
            Sanitized slug string.
        """
        if not slug:
            return f"post-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Replace spaces with hyphens
        slug = slug.strip().replace(" ", "-")

        # Remove special characters but keep hyphens and alphanumeric
        safe_chars = []
        for char in slug:
            if char.isalnum() or char in "-_.":
                safe_chars.append(char)
            else:
                safe_chars.append("-")

        slug = "".join(safe_chars)

        # Remove consecutive hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")

        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        # Truncate to reasonable length
        if len(slug) > 100:
            slug = slug[:100].rstrip("-")

        return slug if slug else "post"

    def _generate_slug(self, article: dict, category: str) -> str:
        """
        Generate a fallback slug if none provided.

        Args:
            article: Article dictionary.
            category: Content category.

        Returns:
            Generated slug string.
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{category}-{timestamp}"