# ========================================
# JobSite — Image Preprocessing Pipeline
# ========================================
"""
Preprocesses scanned newspaper images for optimal OCR accuracy.
Handles: grayscale conversion, thresholding, sharpening, resizing,
and PDF-to-image conversion.
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from pdf2image import convert_from_path

from app.logger import get_logger
from app.utils import get_project_root

logger = get_logger(__name__)


class ImageProcessor:
    """
    Processes raw scanned images/PDFs into OCR-ready images.

    Workflow:
    1. Load image (or convert PDF pages to images)
    2. Resize if too large
    3. Convert to grayscale
    4. Apply adaptive thresholding
    5. Sharpen edges
    6. Return processed PIL Image(s)
    """

    def __init__(self, config: dict):
        """
        Initialize with image processing settings from config.

        Args:
            config: Full configuration dictionary.
        """
        img_cfg = config.get("image", {})
        self.grayscale = img_cfg.get("grayscale", True)
        self.threshold = img_cfg.get("threshold", True)
        self.sharpen = img_cfg.get("sharpen", True)
        self.resize_factor = img_cfg.get("resize_factor", 1.5)
        self.max_dimension = img_cfg.get("max_dimension", 4000)

        # Poppler path for PDF conversion (Windows)
        self.poppler_path = img_cfg.get("poppler_path", None)

        logger.info("ImageProcessor initialized (grayscale=%s, threshold=%s, sharpen=%s)",
                     self.grayscale, self.threshold, self.sharpen)

    def process_file(self, filepath: str) -> list[Image.Image]:
        """
        Process an image or PDF file into OCR-ready PIL Image(s).

        For PDFs, each page becomes a separate image.
        For images, returns a single-element list.

        Args:
            filepath: Absolute path to the image or PDF file.

        Returns:
            List of processed PIL Image objects.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is unsupported.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        ext = os.path.splitext(filepath)[1].lower()
        logger.info("Processing file: %s", os.path.basename(filepath))

        # --- Handle PDF files ---
        if ext == ".pdf":
            return self._process_pdf(filepath)

        # --- Handle image files ---
        return [self._process_image(filepath)]

    def _process_pdf(self, pdf_path: str) -> list[Image.Image]:
        """
        Convert each page of a PDF to a processed image.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of processed PIL Images (one per page).
        """
        logger.info("Converting PDF to images: %s", os.path.basename(pdf_path))

        try:
            # Convert PDF pages to PIL Images at 300 DPI
            kwargs = {"dpi": 300}
            if self.poppler_path:
                kwargs["poppler_path"] = self.poppler_path

            pages = convert_from_path(pdf_path, **kwargs)
            logger.info("PDF has %d page(s)", len(pages))

            processed_pages = []
            for i, page in enumerate(pages):
                logger.debug("Processing PDF page %d/%d", i + 1, len(pages))
                processed = self._apply_preprocessing(page)
                processed_pages.append(processed)

            return processed_pages

        except Exception as e:
            logger.error("PDF conversion failed: %s", str(e))
            raise

    def _process_image(self, image_path: str) -> Image.Image:
        """
        Load and preprocess a single image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Processed PIL Image.
        """
        try:
            img = Image.open(image_path)
            # Convert RGBA to RGB if needed (removes alpha channel)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            return self._apply_preprocessing(img)
        except Exception as e:
            logger.error("Image loading failed for %s: %s", image_path, str(e))
            raise

    def _apply_preprocessing(self, img: Image.Image) -> Image.Image:
        """
        Apply the full preprocessing pipeline to an image.

        Steps: resize → grayscale → threshold → sharpen

        Args:
            img: Raw PIL Image.

        Returns:
            Preprocessed PIL Image ready for OCR.
        """
        # Step 1: Resize if image is too small or too large
        img = self._smart_resize(img)

        # Step 2: Convert to grayscale
        if self.grayscale:
            img = self._to_grayscale(img)

        # Step 3: Apply adaptive thresholding (using OpenCV)
        if self.threshold:
            img = self._apply_threshold(img)

        # Step 4: Sharpen the image
        if self.sharpen:
            img = self._sharpen_image(img)

        logger.debug("Preprocessing complete. Final size: %s", img.size)
        return img

    def _smart_resize(self, img: Image.Image) -> Image.Image:
        """
        Resize image to optimal dimensions for OCR.

        - Upscale small images (< 1000px wide) by resize_factor
        - Downscale very large images to max_dimension

        Args:
            img: Input PIL Image.

        Returns:
            Resized PIL Image.
        """
        width, height = img.size

        # Downscale if too large
        if max(width, height) > self.max_dimension:
            scale = self.max_dimension / max(width, height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            logger.debug("Downscaled to %dx%d", new_width, new_height)

        # Upscale if small (improves OCR on small text)
        elif width < 1000 and self.resize_factor > 1.0:
            new_width = int(width * self.resize_factor)
            new_height = int(height * self.resize_factor)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            logger.debug("Upscaled to %dx%d", new_width, new_height)

        return img

    def _to_grayscale(self, img: Image.Image) -> Image.Image:
        """Convert image to grayscale."""
        return img.convert("L")

    def _apply_threshold(self, img: Image.Image) -> Image.Image:
        """
        Apply adaptive thresholding using OpenCV for cleaner OCR.

        Converts to binary (black text on white background).

        Args:
            img: Grayscale PIL Image.

        Returns:
            Thresholded PIL Image.
        """
        # Convert PIL Image to OpenCV numpy array
        img_array = np.array(img)

        # Ensure single channel (grayscale)
        if len(img_array.shape) == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Apply Gaussian adaptive thresholding
        # This handles uneven lighting common in scanned documents
        thresholded = cv2.adaptiveThreshold(
            img_array,
            255,                           # Max pixel value
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # Method
            cv2.THRESH_BINARY,             # Type
            15,                            # Block size (neighborhood)
            8,                             # Constant subtracted from mean
        )

        # Apply slight morphological closing to connect broken characters
        # This helps with Bangla script which has complex connected shapes
        kernel = np.ones((1, 1), np.uint8)
        thresholded = cv2.morphologyEx(thresholded, cv2.MORPH_CLOSE, kernel)

        return Image.fromarray(thresholded)

    def _sharpen_image(self, img: Image.Image) -> Image.Image:
        """
        Sharpen image edges for clearer character boundaries.

        Args:
            img: PIL Image to sharpen.

        Returns:
            Sharpened PIL Image.
        """
        # Use PIL's built-in SHARPEN filter
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)  # 2.0 = moderate sharpening
        return img

    def create_thumbnail(self, filepath: str, output_dir: str,
                         size: tuple[int, int] = (600, 400)) -> str:
        """
        Create a thumbnail version of the original image for web display.

        Args:
            filepath: Path to original image.
            output_dir: Directory to save thumbnail.
            size: Thumbnail dimensions (width, height).

        Returns:
            Path to the saved thumbnail.
        """
        try:
            img = Image.open(filepath)
            if img.mode == "RGBA":
                img = img.convert("RGB")

            # Use LANCZOS resampling for high quality thumbnails
            img.thumbnail(size, Image.LANCZOS)

            # Generate thumbnail filename
            basename = os.path.splitext(os.path.basename(filepath))[0]
            thumb_filename = f"{basename}_thumb.jpg"
            thumb_path = os.path.join(output_dir, thumb_filename)

            img.save(thumb_path, "JPEG", quality=85, optimize=True)
            logger.info("Thumbnail created: %s", thumb_filename)
            return thumb_path

        except Exception as e:
            logger.error("Thumbnail creation failed: %s", str(e))
            return ""
