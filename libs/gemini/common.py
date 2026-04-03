"""Shared utilities for Gemini API clients — retry logic, model helpers, cost calculation."""

import logging
import time
from typing import Any, Callable, Dict

from google.api_core import exceptions as google_exceptions


logger = logging.getLogger(__name__)


def model_name(name: str) -> str:
    """Strip 'models/' prefix if present."""
    return name.removeprefix("models/")


def retry_with_backoff(
    func: Callable,
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> Any:
    """Execute a function with exponential backoff retry on transient Google API errors.

    Retries on DeadlineExceeded and ServiceUnavailable. All other exceptions propagate immediately.
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (
            google_exceptions.DeadlineExceeded,
            google_exceptions.ServiceUnavailable,
        ) as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed with {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries} retry attempts failed")
        except Exception as e:
            logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
            raise

    raise last_exception  # type: ignore[misc]


def calculate_cost(usage_metadata: Any, model: str) -> Dict[str, Any]:
    """Calculate cost based on token usage and model pricing (per-million rates).

    Uses the model name to look up pricing. Falls back to zero rates for unknown models.
    """
    if not usage_metadata:
        return {}

    prompt_tokens = usage_metadata.prompt_token_count
    candidates_tokens = usage_metadata.candidates_token_count
    total_tokens = getattr(usage_metadata, "total_token_count", prompt_tokens + candidates_tokens)

    model_lower = model.lower()
    input_rate = 0.0
    output_rate = 0.0

    if "gemini-3" in model_lower:
        input_rate = 2.00 if prompt_tokens <= 200000 else 4.00
        output_rate = 12.00 if prompt_tokens <= 200000 else 18.00
    elif "gemini-2.5" in model_lower or "gemini-pro" in model_lower:
        input_rate = 1.25 if prompt_tokens <= 128000 else 2.50
        output_rate = 5.00 if prompt_tokens <= 128000 else 10.00
    elif "flash" in model_lower:
        input_rate = 0.10
        output_rate = 0.40
    elif "imagen" in model_lower:
        # Image generation models — per-million token pricing
        input_rate = 2.50
        output_rate = 5.00

    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (candidates_tokens / 1_000_000) * output_rate
    cost = input_cost + output_cost

    return {
        "prompt_tokens": prompt_tokens,
        "candidates_tokens": candidates_tokens,
        "total_tokens": total_tokens,
        "applied_input_rate": input_rate,
        "applied_output_rate": output_rate,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "estimated_cost_usd": round(cost, 6),
    }
