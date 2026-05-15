# ========================================
# JobSite — Tesseract OCR Engine
# ========================================
"""
Extracts Bangla + English text from preprocessed images using Tesseract OCR.
Handles multi-page documents and performs OCR text cleanup.
"""

import os
import pytesseract
from PIL import Image


from app.logger import get_logger

logger = get_logger(__name__)


class OCREngine:
    """
    Tesseract OCR wrapper optimized for Bangla newspaper text extraction.

    Supports:
    - Bangla (ben) + English (eng) dual-language OCR
    - Configurable PSM and OEM modes
    - OCR text cleanup and normalization
    """

    def __init__(self, config: dict):
        """
        Initialize OCR engine with Tesseract settings.

        Args:
            config: Full configuration dictionary.
        """
        ocr_cfg = config.get("ocr", {})

        # Set Tesseract executable path (required on Windows)
        tesseract_cmd = ocr_cfg.get(
            "tesseract_cmd",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # OCR language setting (ben = Bengali, eng = English)
        self.languages = ocr_cfg.get("languages", "ben+eng")

        # Page Segmentation Mode
        # 3 = Fully automatic page segmentation (default)
        # 6 = Assume a single uniform block of text
        # 4 = Assume a single column of text
        self.psm = ocr_cfg.get("psm", 6)

        # OCR Engine Mode
        # 0 = Legacy engine only
        # 1 = LSTM engine only
        # 2 = Legacy + LSTM
        # 3 = Default (based on availability)
        self.oem = ocr_cfg.get("oem", 3)

        # Verify Tesseract installation
        self._verify_tesseract()

        logger.info("OCR Engine initialized (lang=%s, psm=%d, oem=%d)",
                     self.languages, self.psm, self.oem)

    def _verify_tesseract(self) -> None:
        """
        Verify Tesseract is installed and accessible.

        Raises:
            RuntimeError: If Tesseract is not found or Bengali data is missing.
        """
        try:
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract version: %s", version)

            # Check available languages
            available_langs = pytesseract.get_languages()
            logger.debug("Available OCR languages: %s", available_langs)

            # Warn if Bengali language data is not installed
            if "ben" not in available_langs:
                logger.warning(
                    "⚠️  Bengali (ben) language data not found! "
                    "Install it from: https://github.com/tesseract-ocr/tessdata"
                )

        except Exception as e:
            logger.error("Tesseract verification failed: %s", str(e))
            raise RuntimeError(
                "Tesseract OCR is not installed or not in PATH. "
                "Install from: https://github.com/UB-Mannheim/tesseract/wiki"
            ) from e

    def extract_text(self, images: list[Image.Image]) -> str:
        """
        Extract text from one or more preprocessed images.

        For multi-page documents (PDFs), text from all pages is concatenated.

        Args:
            images: List of preprocessed PIL Image objects.

        Returns:
            Extracted and cleaned text string.
        """
        all_text = []

        for i, img in enumerate(images):
            logger.info("Running OCR on image %d/%d (size: %s)",
                        i + 1, len(images), img.size)

            try:
                # Build Tesseract config string
                custom_config = f"--psm {self.psm} --oem {self.oem}"

                # Run OCR
                raw_text = pytesseract.image_to_string(
                    img,
                    lang=self.languages,
                    config=custom_config,
                )

                # Clean up the extracted text
                cleaned = self._clean_text(raw_text)

                if cleaned.strip():
                    all_text.append(cleaned)
                    logger.info("OCR extracted %d characters from image %d",
                                len(cleaned), i + 1)
                else:
                    logger.warning("OCR produced empty text for image %d", i + 1)

            except Exception as e:
                logger.error("OCR failed on image %d: %s", i + 1, str(e))
                continue

        # Combine text from all pages
        combined_text = "\n\n--- Page Break ---\n\n".join(all_text)

        if not combined_text.strip():
            logger.error("OCR produced no usable text from any image")
            return ""

        logger.info("Total OCR output: %d characters from %d image(s)",
                     len(combined_text), len(images))
        return combined_text

    def extract_with_confidence(self, images: list[Image.Image]) -> dict:
        """
        Extract text with confidence scores for quality assessment.

        Args:
            images: List of preprocessed PIL Images.

        Returns:
            Dictionary with 'text', 'confidence', and 'word_count' keys.
        """
        text = self.extract_text(images)

        # Get detailed OCR data for confidence scoring
        try:
            if images:
                data = pytesseract.image_to_data(
                    images[0],
                    lang=self.languages,
                    config=f"--psm {self.psm} --oem {self.oem}",
                    output_type=pytesseract.Output.DICT,
                )
                confidences = [
                    int(c) for c in data["conf"] if int(c) > 0
                ]
                avg_confidence = (
                    sum(confidences) / len(confidences) if confidences else 0
                )
            else:
                avg_confidence = 0
        except Exception:
            avg_confidence = 0

        word_count = len(text.split()) if text else 0

        return {
            "text": text,
            "confidence": round(avg_confidence, 2),
            "word_count": word_count,
        }

    def _clean_text(self, raw_text: str) -> str:
        """
        Clean OCR output text by removing noise and normalizing whitespace.

        Handles common OCR artifacts in Bangla text:
        - Excessive whitespace and blank lines
        - Stray special characters
        - Broken line joins

        Args:
            raw_text: Raw text output from Tesseract.

        Returns:
            Cleaned text string.
        """
        if not raw_text:
            return ""

        lines = raw_text.split("\n")
        cleaned_lines = []

        for line in lines:
            # Strip leading/trailing whitespace
            line = line.strip()

            # Skip empty lines or lines with only special characters
            if not line:
                continue
            if len(line) < 2 and not line.isalnum():
                continue

            # Remove lines that are just dashes, dots, or underscores
            if all(c in "-_.=~|" for c in line.replace(" ", "")):
                continue

            # Normalize multiple spaces to single space
            while "  " in line:
                line = line.replace("  ", " ")

            cleaned_lines.append(line)

        # Join with newlines, but collapse multiple blank lines
        result = "\n".join(cleaned_lines)

        return result.strip()
