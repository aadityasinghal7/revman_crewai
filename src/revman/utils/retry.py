"""
Retry Logic with Exponential Backoff for RevMan

Provides retry utilities for handling transient failures
in API calls (e.g., LLM rate limits, network timeouts).
"""

import asyncio
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class RetryConfig(BaseModel):
    """Configuration for retry behavior using Pydantic."""
    
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retry attempts"
    )
    initial_delay: float = Field(
        default=1.0,
        gt=0,
        description="Initial delay between retries in seconds"
    )
    max_delay: float = Field(
        default=60.0,
        gt=0,
        description="Maximum delay between retries in seconds"
    )
    exponential_base: float = Field(
        default=2.0,
        gt=1,
        description="Base for exponential backoff calculation"
    )
    retryable_exceptions: Tuple[Type[Exception], ...] = Field(
        default=(Exception,),
        description="Tuple of exception types that should trigger a retry"
    )
    
    class Config:
        arbitrary_types_allowed = True


# Default configuration for LLM API calls
LLM_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    initial_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        # Add specific API exceptions as needed
    )
)


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for the given attempt using exponential backoff.
    
    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
    
    Returns:
        Delay in seconds
    """
    delay = config.initial_delay * (config.exponential_base ** attempt)
    return min(delay, config.max_delay)


def with_retry(
    config: Optional[RetryConfig] = None,
    max_retries: Optional[int] = None,
    initial_delay: Optional[float] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
) -> Callable[[F], F]:
    """
    Decorator that adds retry logic with exponential backoff.
    
    Can be used with either a RetryConfig object or individual parameters.
    
    Args:
        config: RetryConfig object (takes precedence over individual params)
        max_retries: Maximum number of retries
        initial_delay: Initial delay between retries
        retryable_exceptions: Exception types to retry on
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @with_retry(max_retries=3, initial_delay=2.0)
        def call_llm_api():
            return crew.kickoff()
        
        # Or with config object
        @with_retry(config=RetryConfig(max_retries=5))
        def call_llm_api():
            return crew.kickoff()
    """
    # Build config from parameters if not provided
    if config is None:
        config = RetryConfig(
            max_retries=max_retries if max_retries is not None else 3,
            initial_delay=initial_delay if initial_delay is not None else 1.0,
            retryable_exceptions=retryable_exceptions if retryable_exceptions is not None else (Exception,)
        )
    
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"[RETRY] {func.__name__} failed (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {config.max_retries + 1} attempts: {e}"
                        )
            
            # All retries exhausted
            raise last_exception  # type: ignore
        
        return wrapper  # type: ignore
    
    return decorator


def with_retry_async(
    config: Optional[RetryConfig] = None,
    max_retries: Optional[int] = None,
    initial_delay: Optional[float] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
) -> Callable[[F], F]:
    """
    Async version of the retry decorator.
    
    Same parameters as with_retry, but for async functions.
    
    Example:
        @with_retry_async(max_retries=3)
        async def call_llm_api_async():
            return await crew.kickoff_async()
    """
    if config is None:
        config = RetryConfig(
            max_retries=max_retries if max_retries is not None else 3,
            initial_delay=initial_delay if initial_delay is not None else 1.0,
            retryable_exceptions=retryable_exceptions if retryable_exceptions is not None else (Exception,)
        )
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"[RETRY] {func.__name__} failed (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {config.max_retries + 1} attempts: {e}"
                        )
            
            raise last_exception  # type: ignore
        
        return wrapper  # type: ignore
    
    return decorator


class RetryContext:
    """
    Context manager for retry logic when decorators aren't suitable.
    
    Example:
        with RetryContext(max_retries=3) as retry:
            while retry.should_continue():
                try:
                    result = crew.kickoff()
                    break
                except Exception as e:
                    retry.record_failure(e)
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.config = RetryConfig(
            max_retries=max_retries,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base
        )
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
    
    def __enter__(self) -> "RetryContext":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False  # Don't suppress exceptions
    
    def should_continue(self) -> bool:
        """Check if more retry attempts are available."""
        return self.attempt <= self.config.max_retries
    
    def record_failure(self, exception: Exception) -> None:
        """Record a failure and wait before next attempt."""
        self.last_exception = exception
        
        if self.attempt < self.config.max_retries:
            delay = calculate_delay(self.attempt, self.config)
            logger.warning(
                f"[RETRY] Attempt {self.attempt + 1}/{self.config.max_retries + 1} failed: {exception}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
        
        self.attempt += 1
    
    def raise_if_exhausted(self) -> None:
        """Raise the last exception if all retries are exhausted."""
        if self.last_exception and self.attempt > self.config.max_retries:
            raise self.last_exception
