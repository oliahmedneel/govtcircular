# ========================================
# JobSite — AI Structured Data Extractor
# ========================================
"""
Extracts structured fields from OCR text using Gemini AI.
Different extraction prompts for each category.
"""

import json
import time
import google.generativeai as genai
from app.logger import get_logger

logger = get_logger(__name__)

# --- Extraction prompts per category ---
EXTRACTION_PROMPTS = {
    "job_circular": """Extract structured data from this Bangladeshi job circular OCR text.
Return ONLY valid JSON:
{{"organization":"org name","post_name":"position title","num_posts":"number of vacancies or empty","salary":"salary range or empty","age_limit":"age limit or empty","deadline":"application deadline or empty","application_url":"URL if found or empty","location":"job location or empty","qualifications":"required qualifications or empty","experience":"experience requirements or empty","additional_info":"any other important details or empty"}}

OCR TEXT:
{ocr_text}""",

    "tender_notice": """Extract structured data from this Bangladeshi tender notice OCR text.
Return ONLY valid JSON:
{{"authority":"tender issuing authority","work_title":"work/project description","tender_number":"tender/reference number or empty","district":"district/location or empty","submission_deadline":"submission deadline or empty","opening_date":"tender opening date or empty","earnest_money":"earnest money amount or empty","document_price":"tender document price or empty","contact":"contact information or empty","additional_info":"any other details or empty"}}

OCR TEXT:
{ocr_text}""",

    "admission": """Extract structured data from this Bangladeshi admission notice OCR text.
Return ONLY valid JSON:
{{"institution":"institution name","program":"program/course name","deadline":"application deadline or empty","eligibility":"eligibility criteria or empty","application_url":"application URL or empty","exam_date":"exam date if any or empty","seats":"number of seats or empty","fees":"application/tuition fees or empty","contact":"contact info or empty","additional_info":"other details or empty"}}

OCR TEXT:
{ocr_text}""",

    "public_notice": """Extract structured data from this Bangladeshi public/government notice OCR text.
Return ONLY valid JSON:
{{"authority":"issuing authority","subject":"notice subject/title","notice_number":"reference number or empty","date_issued":"issue date or empty","effective_date":"effective date or empty","summary":"brief summary of notice content","affected_parties":"who is affected or empty","action_required":"any action required or empty","contact":"contact info or empty","additional_info":"other details or empty"}}

OCR TEXT:
{ocr_text}""",

    "unknown": """Extract whatever structured data you can from this OCR text.
Return ONLY valid JSON:
{{"title":"best guess at title","authority":"issuing org or empty","date":"any date found or empty","summary":"brief content summary","category_guess":"your best category guess","additional_info":"any other details"}}

OCR TEXT:
{ocr_text}""",
}


class AIExtractor:
    """Extracts structured data from OCR text using Gemini AI."""

    def __init__(self, config: dict):
        ai_cfg = config.get("ai", {})
        api_key = ai_cfg.get("api_key", "")
        if not api_key:
            raise ValueError("Gemini API key not found.")

        genai.configure(api_key=api_key)
        self.model_name = ai_cfg.get("model", "gemini-2.0-flash")
        self.max_retries = ai_cfg.get("max_retries", 3)
        self.retry_delay = ai_cfg.get("retry_delay", 5)

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=genai.GenerationConfig(max_output_tokens=2048, temperature=0.3),
        )
        logger.info("AI Extractor initialized (model=%s)", self.model_name)

    def extract(self, ocr_text: str, category: str) -> dict:
        """
        Extract structured data based on content category.

        Args:
            ocr_text: OCR-extracted text.
            category: Classification category (e.g., 'job_circular').

        Returns:
            Dictionary of extracted structured fields.
        """
        prompt_template = EXTRACTION_PROMPTS.get(category, EXTRACTION_PROMPTS["unknown"])
        prompt = prompt_template.format(ocr_text=ocr_text[:4000])

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Extraction attempt %d/%d for '%s'", attempt, self.max_retries, category)
                response = self.model.generate_content(prompt)
                result = self._parse_json(response.text.strip())
                logger.info("Extracted %d fields for '%s'", len(result), category)
                return result
            except Exception as e:
                logger.error("Extraction error (attempt %d): %s", attempt, str(e))
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        logger.error("Extraction failed for category '%s'", category)
        return {"error": "Extraction failed", "raw_text": ocr_text[:500]}

    def _parse_json(self, text: str) -> dict:
        """Parse JSON from AI response."""
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
