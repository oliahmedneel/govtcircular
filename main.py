# ========================================
# JobSite — Main Pipeline Entry Point
# ========================================
"""
JobSite: Automated Bangladeshi Job & Notice Publishing System.

This is the main entry point that orchestrates the entire pipeline:
  1. Watch uploads directory for new files
  2. Process images/PDFs through OCR
  3. Classify content using AI
  4. Extract structured data
  5. Generate SEO-optimized articles
  6. Create Hugo markdown posts
  7. Deploy via Git to GitHub Pages

Usage:
  python main.py                  # Start file watcher (daemon mode)
  python main.py --once FILE      # Process a single file and exit
  python main.py --watch          # Start watcher explicitly
  python main.py --setup          # Initialize directories and database
"""

import os
import sys
import argparse
import time
import json
from pathlib import Path

from app.logger import get_logger
from app.utils import load_config, ensure_directories, get_project_root, get_supported_extensions
from app.database import Database
from app.watcher import FileWatcher
from app.image_processor import ImageProcessor
from app.ocr_engine import OCREngine
from app.ai_classifier import AIClassifier
from app.ai_extractor import AIExtractor
from app.ai_writer import AIWriter
from app.hugo_writer import HugoWriter
from app.git_deployer import GitDeployer

logger = get_logger(__name__)


class JobSitePipeline:
    """
    Orchestrates the full automation pipeline from file upload to deployment.
    """

    def __init__(self, config: dict):
        """
        Initialize all pipeline components.

        Args:
            config: Full configuration dictionary.
        """
        self.config = config
        self.db = Database(config)
        self.image_processor = ImageProcessor(config)
        self.ocr_engine = OCREngine(config)
        self.classifier = AIClassifier(config)
        self.extractor = AIExtractor(config)
        self.writer = AIWriter(config)
        self.hugo_writer = HugoWriter(config)
        self.git_deployer = GitDeployer(config)

        logger.info("=" * 50)
        logger.info("JobSite Pipeline initialized")
        logger.info("=" * 50)

    def process_file(self, filepath: str) -> dict:
        """
        Process a single file through the full pipeline.

        Args:
            filepath: Absolute path to the uploaded file.

        Returns:
            Dictionary with processing results.
        """
        filename = os.path.basename(filepath)
        logger.info("=" * 50)
        logger.info("Processing: %s", filename)
        logger.info("=" * 50)

        result = {
            "filename": filename,
            "filepath": filepath,
            "success": False,
            "category": None,
            "slug": None,
            "error": None,
            "stages": {},
        }

        try:
            # Step 1: Check for duplicates
            result["stages"]["duplicate_check"] = self._check_duplicate(filepath)
            if result["stages"]["duplicate_check"].get("is_duplicate"):
                logger.warning("Duplicate detected: %s", filename)
                result["error"] = "Duplicate file"
                self._move_to_failed(filepath, "duplicate")
                return result

            # Step 2: Preprocess image/PDF
            logger.info("Stage 1/6: Image preprocessing...")
            images = self.image_processor.process_file(filepath)
            result["stages"]["preprocessing"] = {"pages": len(images)}
            logger.info("  -> %d page(s) extracted", len(images))

            # Step 3: OCR text extraction
            logger.info("Stage 2/6: OCR text extraction...")
            ocr_result = self.ocr_engine.extract_with_confidence(images)
            ocr_text = ocr_result["text"]
            result["stages"]["ocr"] = {
                "char_count": len(ocr_text),
                "word_count": ocr_result["word_count"],
                "confidence": ocr_result["confidence"],
            }
            logger.info("  -> %d chars, %.1f%% confidence",
                        len(ocr_text), ocr_result["confidence"])

            if not ocr_text.strip():
                logger.error("OCR produced no text")
                result["error"] = "OCR produced no text"
                self._move_to_failed(filepath, "no_text")
                return result

            # Step 4: AI Classification
            logger.info("Stage 3/6: AI classification...")
            classification = self.classifier.classify(ocr_text)
            category = classification["category"]
            result["stages"]["classification"] = classification
            logger.info("  -> Category: %s (%.2f%%)",
                        category, classification["confidence"] * 100)

            # Step 5: AI Extraction
            logger.info("Stage 4/6: AI structured extraction...")
            structured_data = self.extractor.extract(ocr_text, category)
            result["stages"]["extraction"] = {"fields": len(structured_data)}
            logger.info("  -> %d fields extracted", len(structured_data))

            # Step 6: AI Article Generation
            logger.info("Stage 5/6: AI article generation...")
            article = self.writer.generate_article(ocr_text, category, structured_data)
            result["stages"]["article"] = {
                "title": article.get("seo_title", "")[:50],
                "slug": article.get("slug", ""),
            }
            logger.info("  -> Title: %s", article.get("seo_title", "")[:60])

            # Step 7: Hugo post creation
            logger.info("Stage 6/6: Hugo post creation...")
            post_path = self.hugo_writer.write_post(article, category, filename)
            result["stages"]["hugo_post"] = {"path": post_path}
            logger.info("  -> Post created: %s", post_path)

            # Create thumbnail if it's an image
            self._create_thumbnail(filepath)

            # Record in database
            self.db.record_file(filepath, category, article.get("slug", ""))

            # Log similarity with existing posts
            similar = self.db.find_similar(filepath, ocr_text)
            if similar:
                logger.info("  -> Similar to existing: %s", similar)

            # ---- SUCCESS ----
            result["category"] = category
            result["slug"] = article.get("slug", "")
            result["success"] = True

            # Move processed file
            self._move_to_processed(filepath)
            logger.info("  -> Completed successfully!")

            # Git auto-deploy
            if self.config.get("git", {}).get("auto_push", True):
                title = article.get("seo_title", filename)
                self.git_deployer.commit_and_push(title)

            return result

        except Exception as e:
            logger.error("Pipeline failed for %s: %s", filename, str(e))
            result["error"] = str(e)
            self._move_to_failed(filepath, "error")
            return result

    def _check_duplicate(self, filepath: str) -> dict:
        """Check if file is a duplicate using hash and text similarity."""
        return self.db.check_duplicate(filepath)

    def _create_thumbnail(self, filepath: str) -> None:
        """Create a thumbnail for image files."""
        try:
            ext = os.path.splitext(filepath)[1].lower()
            if ext != ".pdf":
                thumb_dir = os.path.join(
                    get_project_root(),
                    self.config.get("paths", {}).get("thumbnails", "thumbnails")
                )
                os.makedirs(thumb_dir, exist_ok=True)
                self.image_processor.create_thumbnail(filepath, thumb_dir)
        except Exception as e:
            logger.debug("Thumbnail creation skipped: %s", str(e))

    def _move_to_processed(self, filepath: str) -> None:
        """Move successfully processed file to processed directory."""
        processed_dir = os.path.join(
            get_project_root(),
            self.config.get("paths", {}).get("processed", "processed")
        )
        os.makedirs(processed_dir, exist_ok=True)
        dest = os.path.join(processed_dir, os.path.basename(filepath))
        os.rename(filepath, dest)
        logger.info("Moved to processed: %s", dest)

    def _move_to_failed(self, filepath: str, reason: str) -> None:
        """Move failed file to failed directory."""
        failed_dir = os.path.join(
            get_project_root(),
            self.config.get("paths", {}).get("failed", "failed")
        )
        os.makedirs(failed_dir, exist_ok=True)
        basename = os.path.basename(filepath)
        name, ext = os.path.splitext(basename)
        dest = os.path.join(failed_dir, f"{name}_{reason}{ext}")
        os.rename(filepath, dest)
        logger.info("Moved to failed: %s", dest)

    def start_watcher(self) -> None:
        """Start the file watcher daemon."""
        watcher = FileWatcher(
            self.config,
            callback=self.process_file,
        )
        watcher.start()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="JobSite — Automated Bangladeshi Job & Notice Publishing System"
    )
    parser.add_argument(
        "--once", "-o",
        type=str,
        metavar="FILE",
        help="Process a single file and exit"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Start file watcher daemon"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start the web dashboard"
    )
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="Initialize directories and database"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to custom config file"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config = load_config(args.config)
    project_root = get_project_root()

    # Setup mode: create directories and DB
    if args.setup:
        print("🔧 JobSite Setup")
        print("=" * 50)
        ensure_directories(config)
        db = Database(config)
        db.initialize()
        
        # Hugo Site Setup
        from app.publisher import Publisher
        publisher = Publisher(config)
        print("🚀 Setting up Hugo repository...")
        publisher.setup_repository()
        
        print("✅ Setup complete. Directories, database, and Hugo site initialized.")
        return

    # Ensure directories exist
    ensure_directories(config)

    # Initialize pipeline
    pipeline = JobSitePipeline(config)

    # Single file mode
    if args.once:
        filepath = os.path.abspath(args.once)
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            sys.exit(1)
        print(f"📄 Processing single file: {filepath}")
        result = pipeline.process_file(filepath)
        if result["success"]:
            print(f"✅ Success: {result.get('slug', '')}")
            print(f"   Category: {result.get('category', '')}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        return

    # Web mode
    if args.web:
        print("🌐 Starting JobSite Web Dashboard...")
        print("=" * 50)
        from web_app import app
        app.run(host="0.0.0.0", port=5000, debug=False)
        return

    # Watch mode (default)
    print("👀 JobSite File Watcher")
    print("=" * 50)
    print(f"Watching: {os.path.join(project_root, config.get('paths', {}).get('uploads', 'uploads'))}")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    pipeline.start_watcher()


if __name__ == "__main__":
    main()