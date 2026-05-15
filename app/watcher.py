# ========================================
# JobSite — File Watcher Daemon
# ========================================
"""
Watches the uploads directory for new files and triggers the pipeline.

Uses watchdog's polling observer for cross-platform compatibility.
Supports:
- Delay settling (waits for file copy to complete)
- Extension filtering
- Debouncing rapid file writes
"""

import os
import time
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.logger import get_logger
from app.utils import get_supported_extensions, get_project_root

logger = get_logger(__name__)


class UploadHandler(FileSystemEventHandler):
    """
    Handles file system events in the uploads directory.
    Triggers the pipeline callback when a new file appears.
    """

    def __init__(
        self,
        upload_dir: str,
        callback: Callable,
        supported_extensions: list[str],
        settle_delay: int = 3,
    ):
        """
        Initialize the handler.

        Args:
            upload_dir: Directory to watch.
            callback: Function to call with filepath when a new file is detected.
            supported_extensions: List of acceptable file extensions.
            settle_delay: Seconds to wait after file creation before processing.
        """
        self.upload_dir = upload_dir
        self.callback = callback
        self.supported_extensions = supported_extensions
        self.settle_delay = settle_delay
        self._recently_processed: set = set()

        logger.info(
            "Upload handler initialized (delay=%ds, exts=%s)",
            settle_delay,
            supported_extensions,
        )

    def on_created(self, event) -> None:
        """Called when a file or directory is created."""
        if event.is_directory:
            return
        self._handle_new_file(event.src_path)

    def on_modified(self, event) -> None:
        """Called when a file is modified."""
        if event.is_directory:
            return
        self._handle_new_file(event.src_path)

    def _handle_new_file(self, filepath: str) -> None:
        """
        Process a newly detected file with debouncing.

        Args:
            filepath: Path to the new/modified file.
        """
        # Normalize path
        filepath = os.path.normpath(filepath)

        # Check extension
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in self.supported_extensions:
            logger.debug("Ignored unsupported file: %s", filepath)
            return

        # Debounce: skip if recently processed
        if filepath in self._recently_processed:
            return

        logger.info("New file detected: %s", os.path.basename(filepath))
        self._recently_processed.add(filepath)

        # Wait for file to finish copying (settle delay)
        if self.settle_delay > 0:
            self._wait_for_file(filepath)

        # Trigger the pipeline callback
        try:
            self.callback(filepath)
        except Exception as e:
            logger.error("Callback failed for %s: %s", filepath, str(e))

        # Clean up recently processed set after a delay
        def _cleanup():
            time.sleep(30)
            self._recently_processed.discard(filepath)

        import threading
        threading.Thread(target=_cleanup, daemon=True).start()

    def _wait_for_file(self, filepath: str) -> None:
        """
        Wait for a file to finish being written by checking size stability.

        Args:
            filepath: Path to the file.
        """
        try:
            stable_count = 0
            prev_size = -1

            for _ in range(self.settle_delay * 10):  # Check every 300ms
                time.sleep(0.3)
                if not os.path.exists(filepath):
                    return
                current_size = os.path.getsize(filepath)
                if current_size == prev_size:
                    stable_count += 1
                    if stable_count >= 3:  # Size stable for ~1 second
                        logger.debug("File size stable: %s (%d bytes)",
                                     os.path.basename(filepath), current_size)
                        return
                else:
                    stable_count = 0
                prev_size = current_size

            logger.debug("File settle timeout, processing anyway: %s",
                         os.path.basename(filepath))

        except Exception as e:
            logger.warning("Error waiting for file: %s", str(e))


class FileWatcher:
    """
    File system watcher that monitors uploads directory.
    """

    def __init__(self, config: dict, callback: Callable):
        """
        Initialize the file watcher.

        Args:
            config: Full configuration dictionary.
            callback: Function to call when a new file is detected.
        """
        base_dir = get_project_root()
        upload_dir = os.path.join(
            base_dir,
            config.get("paths", {}).get("uploads", "uploads"),
        )

        watcher_cfg = config.get("watcher", {})
        poll_interval = watcher_cfg.get("poll_interval", 5)
        settle_delay = watcher_cfg.get("settle_delay", 3)

        supported_extensions = get_supported_extensions(config)

        self.upload_dir = upload_dir
        self.poll_interval = poll_interval
        self.callback = callback

        # Ensure upload directory exists
        os.makedirs(upload_dir, exist_ok=True)

        # Process any existing files in upload dir
        self._process_existing_files(upload_dir, supported_extensions, callback)

        # Set up watchdog observer
        handler = UploadHandler(
            upload_dir=upload_dir,
            callback=callback,
            supported_extensions=supported_extensions,
            settle_delay=settle_delay,
        )

        self.observer = Observer()
        self.observer.schedule(handler, upload_dir, recursive=False)

        logger.info(
            "FileWatcher initialized (dir=%s, interval=%ds)",
            upload_dir,
            poll_interval,
        )

    def _process_existing_files(
        self,
        upload_dir: str,
        supported_extensions: list[str],
        callback: Callable,
    ) -> None:
        """
        Process any files already in the upload directory on startup.

        Args:
            upload_dir: Upload directory path.
            supported_extensions: List of supported file extensions.
            callback: Pipeline callback function.
        """
        try:
            for filename in os.listdir(upload_dir):
                filepath = os.path.join(upload_dir, filename)
                if os.path.isfile(filepath):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in supported_extensions:
                        logger.info("Processing existing file: %s", filename)
                        try:
                            callback(filepath)
                        except Exception as e:
                            logger.error("Failed to process existing file %s: %s",
                                         filename, str(e))
        except Exception as e:
            logger.warning("Error checking existing files: %s", str(e))

    def start(self) -> None:
        """Start watching the upload directory."""
        logger.info("Starting file watcher for: %s", self.upload_dir)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
        except KeyboardInterrupt:
            logger.info("File watcher stopped by user")
            self.stop()

    def stop(self) -> None:
        """Stop the file watcher."""
        logger.info("Stopping file watcher...")
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")