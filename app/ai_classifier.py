# ========================================
# JobSite — AI Content Classifier
# ========================================
"""
Uses Google Gemini AI to classify OCR-extracted text into categories:
Job Circular, Tender Notice, Admission, Public Notice, Unknown.
"""

import os
import json
import time
import google.generativeai as genai
from app.logger import get_logger

logger = get_logger(__name__)

CLASSIFICATION_PROMPT = """You are an expert classifier for Bangladeshi newspaper content.
Analyze this OCR text from a Bangladeshi newspaper. Classify into ONE category:
1. "job_circular" — Job vacancy, recruitment, employment
2. "tender_notice" — Tender, procurement, bidding
3. "admission" — Educational admission, enrollment
4. "public_notice" — Government/public announcement
5. "unknown" — Cannot determine

Keywords: নিয়োগ,পদ,বেতন,আবেদন=job | দরপত্র,টেন্ডার,ক্রয়=tender | ভর্তি,শিক্ষার্থী=admission | বিজ্ঞপ্তি,আদেশ,প্রজ্ঞাপন=public

Respond with ONLY valid JSON:
{{"category":"job_circular","confidence":0.95,"reason":"Brief English explanation"}}

--- OCR TEXT ---
{ocr_text}
--- END ---"""


class AIClassifier:
    """Classifies newspaper content using Google Gemini AI."""

    VALID_CATEGORIES = ["job_circular", "tender_notice", "admission", "public_notice", "unknown"]

    def __init__(self, config: dict):
        ai_cfg = config.get("ai", {})
        api_key = ai_cfg.get("api_key", "")
        if not api_key:
            raise ValueError("Gemini API key not found. Set GEMINI_API_KEY in .env file.")

        genai.configure(api_key=api_key)
        self.model_name = ai_cfg.get("model", "gemini-2.0-flash")
        self.max_retries = ai_cfg.get("max_retries", 3)
        self.retry_delay = ai_cfg.get("retry_delay", 5)

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=genai.GenerationConfig(max_output_tokens=1024, temperature=0.3),
        )

        # Load custom prompt if available
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    config.get("paths", {}).get("prompts", "prompts"))
        prompt_file = os.path.join(prompts_dir, "classification.txt")
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
        else:
            self.prompt_template = CLASSIFICATION_PROMPT

        logger.info("AI Classifier initialized (model=%s)", self.model_name)

    def classify(self, ocr_text: str) -> dict:
        """Classify OCR text into a content category. Returns dict with category, confidence, reason."""
        if not ocr_text or len(ocr_text.strip()) < 20:
            return {"category": "unknown", "confidence": 0.0, "reason": "Text too short"}

        prompt = self.prompt_template.format(ocr_text=ocr_text[:3000])

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Classification attempt %d/%d", attempt, self.max_retries)
                response = self.model.generate_content(prompt)
                result = self._parse_response(response.text.strip())
                if result["category"] not in self.VALID_CATEGORIES:
                    result["category"] = "unknown"
                logger.info("Classified as: %s (%.2f)", result["category"], result["confidence"])
                return result
            except Exception as e:
                logger.error("Classification error (attempt %d): %s", attempt, str(e))
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        return {"category": "unknown", "confidence": 0.0, "reason": "Failed after retries"}

    def _parse_response(self, text: str) -> dict:
        """Parse JSON from Gemini response, handling code blocks."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        if "```json" in text:
            return json.loads(text.split("```json")[1].split("```")[0].strip())
        if "```" in text:
            return json.loads(text.split("```")[1].split("```")[0].strip())
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise json.JSONDecodeError("No JSON found", text, 0)
