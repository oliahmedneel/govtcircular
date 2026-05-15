# ========================================
# JobSite — AI Article Writer
# ========================================
"""
Generates SEO-optimized Bangla articles using Gemini AI.
Produces: title, slug, meta description, tags, and full article body.
"""

import json
import time
import google.generativeai as genai
from app.logger import get_logger

logger = get_logger(__name__)

ARTICLE_PROMPT = """You are an expert Bangladeshi SEO content writer.
Write a complete, human-quality, SEO-optimized Bangla article for a website about this {category_bn}.

STRUCTURED DATA:
{structured_data}

RAW OCR TEXT (for additional context):
{ocr_text}

REQUIREMENTS:
1. Write the article body in Bangla (Bengali script)
2. Make it read naturally — NOT like AI-generated content
3. Include all important information from the structured data
4. Use proper Bangla typography and formatting
5. Add bullet points for key details (deadline, salary, eligibility, etc.)
6. Include a brief summary at the start
7. End with application/action instructions
8. Article should be 300-600 words

RESPOND WITH ONLY THIS JSON FORMAT:
{{
  "seo_title": "SEO-optimized Bangla title (50-60 chars ideal)",
  "slug": "english-slug-with-keywords-and-date",
  "meta_description": "Compelling Bangla meta description (150-160 chars)",
  "summary": "2-3 sentence Bangla summary for listing pages",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "article_body": "Full Bangla article in markdown format with ## headings and bullet points"
}}"""


class AIWriter:
    """Generates SEO-optimized Bangla articles using Gemini AI."""

    CATEGORY_BN = {
        "job_circular": "চাকরির বিজ্ঞপ্তি",
        "tender_notice": "দরপত্র বিজ্ঞপ্তি",
        "admission": "ভর্তি বিজ্ঞপ্তি",
        "public_notice": "সরকারি বিজ্ঞপ্তি",
        "unknown": "বিজ্ঞপ্তি",
    }

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
            generation_config=genai.GenerationConfig(
                max_output_tokens=4096,
                temperature=0.7,  # More creative for article writing
            ),
        )
        self.categories_cfg = config.get("categories", {})
        logger.info("AI Writer initialized (model=%s)", self.model_name)

    def generate_article(self, ocr_text: str, category: str, structured_data: dict) -> dict:
        """
        Generate a complete SEO-optimized article.

        Args:
            ocr_text: Original OCR text for context.
            category: Content category key (e.g., 'job_circular').
            structured_data: Extracted structured data dict.

        Returns:
            Dict with seo_title, slug, meta_description, summary, tags, article_body.
        """
        category_bn = self.CATEGORY_BN.get(category, "বিজ্ঞপ্তি")

        prompt = ARTICLE_PROMPT.format(
            category_bn=category_bn,
            structured_data=json.dumps(structured_data, ensure_ascii=False, indent=2),
            ocr_text=ocr_text[:2000],
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Article generation attempt %d/%d", attempt, self.max_retries)
                response = self.model.generate_content(prompt)
                result = self._parse_json(response.text.strip())

                # Validate required fields
                required = ["seo_title", "slug", "meta_description", "article_body"]
                for field in required:
                    if field not in result or not result[field]:
                        raise ValueError(f"Missing required field: {field}")

                # Ensure tags is a list
                if isinstance(result.get("tags"), str):
                    result["tags"] = [t.strip() for t in result["tags"].split(",")]
                if not result.get("tags"):
                    result["tags"] = [category_bn]

                # Ensure summary exists
                if not result.get("summary"):
                    result["summary"] = result["meta_description"]

                logger.info("Article generated: %s", result["seo_title"][:50])
                return result

            except Exception as e:
                logger.error("Article generation error (attempt %d): %s", attempt, str(e))
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        logger.error("Article generation failed after all attempts")
        return self._fallback_article(ocr_text, category, structured_data)

    def _fallback_article(self, ocr_text: str, category: str, data: dict) -> dict:
        """Generate a minimal fallback article if AI fails."""
        category_bn = self.CATEGORY_BN.get(category, "বিজ্ঞপ্তি")
        title = data.get("organization", data.get("authority", data.get("institution", "বিজ্ঞপ্তি")))
        return {
            "seo_title": f"{title} — {category_bn}",
            "slug": f"{category}-notice-{int(time.time())}",
            "meta_description": f"{title} {category_bn} — বিস্তারিত তথ্য দেখুন।",
            "summary": f"{title} হতে {category_bn} প্রকাশিত হয়েছে।",
            "tags": [category_bn],
            "article_body": f"## {title}\n\n{ocr_text[:1000]}",
        }

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
