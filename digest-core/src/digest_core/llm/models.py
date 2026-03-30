"""
Strict LLM response models with Pydantic validation.
"""

import json
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError
import structlog

logger = structlog.get_logger()


class EvidenceItem(BaseModel):
    """Evidence reference item."""

    thread_id: str
    message_ids: List[str]
    quote: str = Field(..., max_length=4000)


class SummaryItem(BaseModel):
    """Summary item with evidence reference."""

    title: str
    detail: str
    evidence_ref: Optional[str] = None  # thread_id or message_id


class LLMResponse(BaseModel):
    """Strict LLM response model for validation."""

    version: Literal["v1", "1.0"] = "v1"
    evidence: List[EvidenceItem] = Field(default_factory=list)
    summary: List[SummaryItem] = Field(default_factory=list)
    notes: Optional[str] = None


def parse_llm_json(text: str, *, strict: bool = True) -> LLMResponse:
    """
    Parse and validate LLM JSON response with strict Pydantic validation.

    Args:
        text: Raw JSON text from LLM
        strict: If True, raise on validation errors. If False, attempt minimal repair.

    Returns:
        Validated LLMResponse object

    Raises:
        ValueError: If JSON is invalid and strict=True or repair fails
    """
    try:
        # Try direct parsing first
        data = json.loads(text)
        return LLMResponse.model_validate(data)

    except (json.JSONDecodeError, ValidationError) as err:
        error_msg = str(err)
        preview = text[:300] if len(text) > 300 else text

        logger.warning(
            "LLM JSON parse/validate failed",
            error=error_msg,
            preview=preview,
            strict=strict,
        )

        if strict:
            raise ValueError(f"Invalid LLM JSON response: {error_msg}")

        # Attempt minimal repair if not strict
        try:
            repaired = minimal_json_repair(text)
            data = json.loads(repaired)
            return LLMResponse.model_validate(data)

        except Exception as repair_err:
            logger.error(
                "JSON repair failed",
                original_error=error_msg,
                repair_error=str(repair_err),
                preview=preview,
            )
            raise ValueError(f"JSON repair failed: {repair_err}")


def minimal_json_repair(text: str) -> str:
    """
    Minimal JSON repair - only fixes trivial issues.

    Fixes:
    - Remove markdown code blocks
    - Trim to last closing brace
    - Remove trailing commas

    Args:
        text: Raw JSON-like text

    Returns:
        Cleaned JSON string
    """
    import re

    # Remove markdown code blocks
    text = re.sub(r"```\s*json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()

    # Trim to last closing brace if present
    if "}" in text:
        last_brace = text.rfind("}")
        text = text[: last_brace + 1]

    # Remove trailing commas before ] or }
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    return text


def call_llm_and_parse(
    prompt: str, llm_callable, *, strict: bool = True, max_retries: int = 3
) -> LLMResponse:
    """
    Call LLM and parse response with retry logic.

    Args:
        prompt: User prompt
        llm_callable: Function that calls LLM and returns raw text
        strict: Enforce strict validation
        max_retries: Maximum retry attempts

    Returns:
        Validated LLMResponse

    Raises:
        RuntimeError: If all retries fail
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            raw = llm_callable(prompt)
            return parse_llm_json(raw, strict=strict)

        except Exception as err:
            last_error = err
            logger.info(
                "LLM parse attempt failed, retrying",
                attempt=attempt,
                max_retries=max_retries,
                error=str(err),
            )

            # Add hint to prompt on retry
            if attempt < max_retries:
                prompt += (
                    "\n\nIMPORTANT: Return ONLY valid JSON per schema. No markdown, no code blocks."
                )

    raise RuntimeError(f"LLM returned invalid JSON after {max_retries} retries: {last_error}")
