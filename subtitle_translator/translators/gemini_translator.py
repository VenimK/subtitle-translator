"""Google Gemini translator implementation."""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional

import google.generativeai as genai

from .base import BaseTranslator

logger = logging.getLogger(__name__)

# Pricing per 1,000 tokens in USD (placeholders, adjust as needed)
GEMINI_PRICING = {
    'gemini-2.5-flash-preview-05-20': {
        'input': 0.000125,
        'output': 0.000375,
    },
    'gemini-1.5-pro-latest': {
        'input': 0.00125,
        'output': 0.00375,
    },
}

class GeminiTranslator(BaseTranslator):
    """Translator using the Google Gemini API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Gemini translator."""
        super().__init__(config)
        # Determine API key source
        api_key = self.config.get('api_key')
        key_source = "GUI"

        if not api_key:
            api_key = os.environ.get('GOOGLE_API_KEY')
            key_source = "environment variable"

        self.api_key = api_key

        if self.api_key:
            genai.configure(api_key=self.api_key)
            masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "..."
            logger.info(f"Using Gemini API key from {key_source}: {masked_key}")
        else:
            logger.warning("No Gemini API key found in GUI settings or environment variable. Translation will likely fail.")

        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        self.prompt_template = self.config.get(
            'prompt_template',
            "Translate the following text from {source_language} to {target_language}. Please provide only the translated text, without any additional explanations or context. Maintain the original meaning and tone as much as possible."
        )
        self.tone = self.config.get('tone', '')

    async def translate_text(
        self, text: str, source_language: str, target_language: str, **kwargs
    ) -> str:
        """Translate a single text string using Gemini."""
        if not self.api_key:
            raise ConnectionError("Gemini API key not configured.")

        prompt = self.prompt_template.format(
            source_language=source_language,
            target_language=target_language,
            LANG=target_language,
            TEXT=text,
            TONE=self.tone
        )
        try:
            response = await self.model.generate_content_async(prompt)
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                prompt_tokens = response.usage_metadata.prompt_token_count
                candidates_tokens = response.usage_metadata.candidates_token_count
                total_tokens = response.usage_metadata.total_token_count

                model_name = self.model.model_name.split('/')[-1]
                pricing = GEMINI_PRICING.get(model_name)
                cost_info = ""
                if pricing:
                    input_cost = (prompt_tokens / 1000) * pricing['input']
                    output_cost = (candidates_tokens / 1000) * pricing['output']
                    total_cost = input_cost + output_cost
                    cost_info = f" | Cost: ${total_cost:.6f}"
                
                logger.info(f"Gemini token usage: {prompt_tokens} (prompt) + {candidates_tokens} (candidates) = {total_tokens} total tokens.{cost_info}")
            return response.text
        except Exception as e:
            logger.error(f"Gemini translation failed: {e}", exc_info=True)
            raise

    async def _translate_batch(
        self, texts: List[str], source_language: str, target_language: str, **kwargs
    ) -> List[str]:
        """Translate a batch of texts using Gemini, running requests concurrently."""
        if not self.api_key:
            raise ConnectionError("Gemini API key not configured.")

        total_prompt_tokens = 0
        total_candidates_tokens = 0
        total_cost = 0.0

        async def _translate(text):
            nonlocal total_prompt_tokens, total_candidates_tokens, total_cost
            prompt = self.prompt_template.format(
                source_language=source_language,
                target_language=target_language,
                LANG=target_language,
                TEXT=text,
                TONE=self.tone
            )
            try:
                response = await self.model.generate_content_async(prompt)
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    prompt_tokens = response.usage_metadata.prompt_token_count
                    candidates_tokens = response.usage_metadata.candidates_token_count
                    total_prompt_tokens += prompt_tokens
                    total_candidates_tokens += candidates_tokens

                    model_name = self.model.model_name.split('/')[-1]
                    pricing = GEMINI_PRICING.get(model_name)
                    if pricing:
                        input_cost = (prompt_tokens / 1000) * pricing['input']
                        output_cost = (candidates_tokens / 1000) * pricing['output']
                        total_cost += input_cost + output_cost

                return response.text
            except Exception as e:
                logger.error(f"Gemini translation for '{text}' failed: {e}")
                return ""  # Return empty string on failure

        tasks = [_translate(text) for text in texts]
        translated_texts = await asyncio.gather(*tasks)
        
        total_tokens = total_prompt_tokens + total_candidates_tokens
        cost_info = f" | Total Cost: ${total_cost:.6f}" if total_cost > 0 else ""
        logger.info(f"Gemini batch translation completed. Total tokens: {total_prompt_tokens} (prompt) + {total_candidates_tokens} (candidates) = {total_tokens}.{cost_info}")
        
        return translated_texts
