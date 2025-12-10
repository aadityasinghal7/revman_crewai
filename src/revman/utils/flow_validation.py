"""
Flow Validation Utilities for RevMan

Provides decorators and utilities for validating Flow step outputs
following CrewAI Flow patterns with Pydantic validation.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel, Field, ValidationError
import logging

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class FlowValidationError(Exception):
    """
    Raised when a Flow step fails validation.
    
    This exception is designed to stop the flow execution
    and provide clear error messages about what validation failed.
    """
    
    def __init__(
        self,
        step_name: str,
        message: str,
        validation_errors: Optional[List[Dict[str, Any]]] = None
    ):
        self.step_name = step_name
        self.message = message
        self.validation_errors = validation_errors or []
        super().__init__(f"[{step_name}] {message}")


class StepValidationConfig(BaseModel):
    """Configuration for step validation using Pydantic."""
    
    required_state_keys: List[str] = Field(
        default_factory=list,
        description="State attributes that must exist and be non-empty after step execution"
    )
    min_items: Dict[str, int] = Field(
        default_factory=dict,
        description="Minimum item counts for list/dict state attributes"
    )
    fail_on_empty: bool = Field(
        default=True,
        description="Whether to fail if required state keys are empty collections"
    )


def validate_step(
    required_state_keys: Optional[List[str]] = None,
    min_items: Optional[Dict[str, int]] = None,
    fail_on_empty: bool = True
) -> Callable[[F], F]:
    """
    Decorator for Flow steps that validates state after execution.
    
    This decorator wraps CrewAI Flow methods decorated with @listen or @start
    and validates the Flow's state after the step completes.
    
    Args:
        required_state_keys: List of state attribute names that must exist and be populated
        min_items: Dict mapping state attribute names to minimum item counts
        fail_on_empty: If True, empty collections in required keys will cause failure
    
    Returns:
        Decorated function with validation
    
    Raises:
        FlowValidationError: If validation fails
    
    Example:
        @listen(trigger)
        @validate_step(
            required_state_keys=["price_changes_categorized"],
            min_items={"price_changes_categorized": 1}
        )
        def process_excel(self):
            # ... implementation ...
    """
    config = StepValidationConfig(
        required_state_keys=required_state_keys or [],
        min_items=min_items or {},
        fail_on_empty=fail_on_empty
    )
    
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            step_name = func.__name__
            
            logger.info(f"[FLOW] Executing step: {step_name}")
            
            # Execute the step
            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"[FLOW] Step '{step_name}' raised exception: {e}")
                raise
            
            # Validate state after execution
            _validate_state(self, step_name, config)
            
            logger.info(f"[FLOW] Step '{step_name}' completed and validated successfully")
            return result
        
        return wrapper  # type: ignore
    
    return decorator


def _validate_state(flow_instance: Any, step_name: str, config: StepValidationConfig) -> None:
    """
    Validate the flow's state against the configuration.
    
    Args:
        flow_instance: The Flow instance (self)
        step_name: Name of the step being validated
        config: Validation configuration
    
    Raises:
        FlowValidationError: If validation fails
    """
    errors: List[Dict[str, Any]] = []
    
    # Check required state keys
    for key in config.required_state_keys:
        # Check if it's a private attribute (self._key) or state attribute (self.state.key)
        if key.startswith("_"):
            value = getattr(flow_instance, key, None)
        elif hasattr(flow_instance, "state"):
            value = getattr(flow_instance.state, key, None)
        else:
            value = getattr(flow_instance, key, None)
        
        if value is None:
            errors.append({
                "field": key,
                "error": "Required state attribute is None",
                "type": "missing_value"
            })
        elif config.fail_on_empty and isinstance(value, (dict, list)) and len(value) == 0:
            errors.append({
                "field": key,
                "error": "Required state attribute is empty",
                "type": "empty_collection"
            })
    
    # Check minimum item counts
    for key, min_count in config.min_items.items():
        if key.startswith("_"):
            value = getattr(flow_instance, key, None)
        elif hasattr(flow_instance, "state"):
            value = getattr(flow_instance.state, key, None)
        else:
            value = getattr(flow_instance, key, None)
        
        if value is not None:
            count = len(value) if isinstance(value, (dict, list)) else 0
            if count < min_count:
                errors.append({
                    "field": key,
                    "error": f"Expected at least {min_count} items, got {count}",
                    "type": "insufficient_items",
                    "expected": min_count,
                    "actual": count
                })
    
    # Raise if validation failed
    if errors:
        error_summary = "; ".join(f"{e['field']}: {e['error']}" for e in errors)
        raise FlowValidationError(
            step_name=step_name,
            message=f"State validation failed: {error_summary}",
            validation_errors=errors
        )


def validate_crew_output(
    min_length: int = 1,
    required_keys: Optional[List[str]] = None,
    error_indicators: Optional[List[str]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to validate the output of a Crew kickoff.
    
    Args:
        min_length: Minimum length of raw output string
        required_keys: Keys that must exist if output is JSON
        error_indicators: Strings that indicate an error in the output
    
    Returns:
        Decorated function
    
    Example:
        @validate_crew_output(min_length=10, error_indicators=["error", "failed"])
        def run_my_crew(self):
            return MyCrew().crew().kickoff(inputs={...})
    """
    required_keys = required_keys or []
    error_indicators = error_indicators or ["error", "Error", "ERROR", "failed", "Failed"]
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Get raw output
            raw_output = result.raw if hasattr(result, "raw") else str(result)
            
            # Check minimum length
            if len(raw_output) < min_length:
                raise FlowValidationError(
                    step_name=func.__name__,
                    message=f"Crew output too short: {len(raw_output)} chars (min: {min_length})"
                )
            
            # Check for error indicators
            for indicator in error_indicators:
                if indicator in raw_output[:200]:  # Check first 200 chars
                    raise FlowValidationError(
                        step_name=func.__name__,
                        message=f"Crew output contains error indicator: '{indicator}'"
                    )
            
            return result
        
        return wrapper
    
    return decorator
