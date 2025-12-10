"""
Validated Base Tool for RevMan

Provides a base class for all CrewAI tools that includes:
- Automatic output validation
- Structured error handling (fail-fast, no swallowing)
- Logging integration
- Pydantic-based configuration

This follows CrewAI's BaseTool pattern while adding production-ready
validation and error handling.
"""

import json
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)


class ToolValidationError(Exception):
    """
    Raised when a tool's output fails validation.
    
    Unlike returning {"error": ...}, this exception will propagate
    to CrewAI, signaling that the tool execution actually failed.
    """
    
    def __init__(self, tool_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.tool_name = tool_name
        self.message = message
        self.details = details or {}
        super().__init__(f"[{tool_name}] {message}")


class ToolOutputValidation(BaseModel):
    """Configuration for tool output validation using Pydantic."""
    
    min_output_items: int = Field(
        default=0,
        ge=0,
        description="Minimum number of items the tool must produce"
    )
    required_output_keys: List[str] = Field(
        default_factory=list,
        description="Keys that must exist in the output dictionary"
    )
    fail_on_error_key: bool = Field(
        default=True,
        description="If True, fail when output contains 'error' key"
    )


class ValidatedBaseTool(BaseTool):
    """
    Base class for RevMan tools with built-in validation.
    
    This class extends CrewAI's BaseTool to add:
    1. Automatic output validation based on declarative rules
    2. Fail-fast error handling (exceptions instead of error dicts)
    3. Structured logging
    
    Subclasses should:
    1. Define `name`, `description`, and `args_schema` as usual
    2. Set validation rules via class attributes (min_output_items, required_output_keys)
    3. Implement `_execute()` instead of `_run()`
    
    Example:
        class MyTool(ValidatedBaseTool):
            name: str = "My Tool"
            description: str = "Does something useful"
            args_schema: Type[BaseModel] = MyToolInput
            
            # Validation configuration
            min_output_items: int = 1
            required_output_keys: List[str] = ["result", "count"]
            
            def _execute(self, **kwargs) -> Dict[str, Any]:
                # Your implementation - just return data, don't handle errors
                return {"result": "...", "count": 10}
            
            def _count_items(self, result: Dict[str, Any]) -> int:
                return result.get("count", 0)
    """
    
    # Validation configuration - override in subclasses
    min_output_items: int = 0
    required_output_keys: List[str] = []
    fail_on_error_key: bool = True
    
    def _run(self, **kwargs) -> str:
        """
        Main entry point called by CrewAI.
        
        This method wraps _execute() with validation and error handling.
        Subclasses should NOT override this method.
        """
        tool_name = self.name
        
        logger.info(f"[TOOL] {tool_name}: Starting execution")
        logger.debug(f"[TOOL] {tool_name}: Input kwargs: {kwargs}")
        
        try:
            # Call the actual implementation
            result = self._execute(**kwargs)
            
            # Normalize result to dict
            if isinstance(result, str):
                try:
                    result_dict = json.loads(result)
                except json.JSONDecodeError:
                    # String result that's not JSON - wrap it
                    result_dict = {"raw_output": result}
            elif isinstance(result, dict):
                result_dict = result
            else:
                result_dict = {"raw_output": str(result)}
            
            # Validate the result
            self._validate_output(result_dict)
            
            # Log success
            item_count = self._count_items(result_dict)
            logger.info(f"[TOOL] {tool_name}: Success - produced {item_count} items")
            
            # Return as JSON string (CrewAI expects string output)
            return json.dumps(result_dict, indent=2, default=str)
        
        except ToolValidationError:
            # Re-raise validation errors as-is
            raise
        
        except FileNotFoundError as e:
            # Convert to ToolValidationError for clear messaging
            logger.error(f"[TOOL] {tool_name}: File not found - {e}")
            raise ToolValidationError(
                tool_name=tool_name,
                message=f"Required file not found: {e}",
                details={"exception_type": "FileNotFoundError"}
            )
        
        except ValueError as e:
            # Convert to ToolValidationError for clear messaging
            logger.error(f"[TOOL] {tool_name}: Value error - {e}")
            raise ToolValidationError(
                tool_name=tool_name,
                message=f"Invalid value: {e}",
                details={"exception_type": "ValueError"}
            )
        
        except Exception as e:
            # Log and re-raise unexpected errors (no swallowing!)
            logger.error(f"[TOOL] {tool_name}: Unexpected error - {e}", exc_info=True)
            raise ToolValidationError(
                tool_name=tool_name,
                message=f"Unexpected error: {e}",
                details={"exception_type": type(e).__name__}
            )
    
    @abstractmethod
    def _execute(self, **kwargs) -> Union[Dict[str, Any], str]:
        """
        Implement your tool's logic here.
        
        This method should:
        1. Perform the actual work
        2. Return a dictionary with results
        3. NOT catch exceptions (let them propagate for proper error handling)
        4. NOT return error dictionaries (raise exceptions instead)
        
        Args:
            **kwargs: Arguments matching the args_schema
        
        Returns:
            Dictionary with results, or a JSON string
        
        Raises:
            FileNotFoundError: If a required file is missing
            ValueError: If input validation fails
            Any other exception: Will be caught and converted to ToolValidationError
        """
        pass
    
    def _validate_output(self, result: Dict[str, Any]) -> None:
        """
        Validate the tool's output against configured rules.
        
        Args:
            result: The output dictionary to validate
        
        Raises:
            ToolValidationError: If validation fails
        """
        tool_name = self.name
        
        # Check for error key
        if self.fail_on_error_key and "error" in result:
            raise ToolValidationError(
                tool_name=tool_name,
                message=f"Tool returned error: {result.get('error')}",
                details={"error_key": result.get("error")}
            )
        
        # Check required keys
        for key in self.required_output_keys:
            if key not in result:
                raise ToolValidationError(
                    tool_name=tool_name,
                    message=f"Missing required output key: '{key}'",
                    details={"missing_key": key, "available_keys": list(result.keys())}
                )
        
        # Check minimum items
        if self.min_output_items > 0:
            item_count = self._count_items(result)
            if item_count < self.min_output_items:
                raise ToolValidationError(
                    tool_name=tool_name,
                    message=f"Produced {item_count} items, minimum required: {self.min_output_items}",
                    details={"item_count": item_count, "min_required": self.min_output_items}
                )
    
    def _count_items(self, result: Dict[str, Any]) -> int:
        """
        Count the number of "items" in the output.
        
        Override this method in subclasses to define custom counting logic.
        
        The default implementation:
        1. Checks for common count keys (total_records, count, formulas_added, etc.)
        2. Falls back to summing lengths of list values
        
        Args:
            result: The output dictionary
        
        Returns:
            Number of items produced
        """
        # Check for common count keys
        count_keys = [
            "total_records", "count", "formulas_added", "total_skus",
            "total_products", "total_anomalies_detected", "total_skus_forecasted"
        ]
        
        for key in count_keys:
            if key in result:
                value = result[key]
                if isinstance(value, (int, float)):
                    return int(value)
        
        # Fall back to summing list lengths
        total = 0
        for value in result.values():
            if isinstance(value, list):
                total += len(value)
        
        return total if total > 0 else 1  # Return 1 if we have a result but no lists
    
    def tool(self):
        """Return self for CrewAI compatibility."""
        return self
