"""
Structured Logging Configuration for RevMan

Provides JSON-formatted logs with proper log levels, timestamps,
and contextual information for cloud deployment and monitoring.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LogRecord(BaseModel):
    """Pydantic model for structured log records."""
    timestamp: str = Field(description="ISO format timestamp")
    level: str = Field(description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    logger: str = Field(description="Logger name")
    message: str = Field(description="Log message")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs logs in JSON format for easy parsing by log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record = LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            context=getattr(record, "context", {})
        )
        
        # Add exception info if present
        if record.exc_info:
            log_record.context["exception"] = self.formatException(record.exc_info)
        
        return log_record.model_dump_json()


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output during development.
    """
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m"       # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format: [TIMESTAMP] [LEVEL] [LOGGER] Message
        formatted = f"[{timestamp}] {color}[{record.levelname}]{reset} [{record.name}] {record.getMessage()}"
        
        # Add context if present
        context = getattr(record, "context", {})
        if context:
            formatted += f" | context={json.dumps(context)}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging for the RevMan application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output logs in JSON format (for production)
        log_file: Optional file path to write logs to
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter based on environment
    formatter = JSONFormatter() if json_format else ConsoleFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds context to all log messages.
    Useful for adding flow_id, step_name, etc. to all logs in a context.
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        # Merge extra context
        extra = kwargs.get("extra", {})
        extra["context"] = {**self.extra, **extra.get("context", {})}
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(name: str, **context: Any) -> LoggerAdapter:
    """
    Get a logger with persistent context attached.
    
    Args:
        name: Logger name
        **context: Key-value pairs to attach to all log messages
    
    Returns:
        Logger adapter with context
    
    Example:
        logger = get_context_logger(__name__, flow_id="abc123", step="process_excel")
        logger.info("Processing started")  # Will include flow_id and step in output
    """
    base_logger = get_logger(name)
    return LoggerAdapter(base_logger, context)
